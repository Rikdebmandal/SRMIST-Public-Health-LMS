"""Attendance aggregation and alert generation."""
from collections import defaultdict

from django.db.models import Count, Q

from apps.attendance.models import AttendanceAlert, AttendancePolicy, AttendanceRecord
from apps.core.calculations import attendance_percentage, attendance_status, sessions_needed_to_reach

Status = AttendanceRecord.Status


def summarise(records_qs, policy):
    """Reduce a record queryset to counts plus the derived percentage."""
    counts = records_qs.aggregate(
        present=Count("id", filter=Q(status=Status.PRESENT)),
        absent=Count("id", filter=Q(status=Status.ABSENT)),
        late=Count("id", filter=Q(status=Status.LATE)),
        excused=Count("id", filter=Q(status=Status.EXCUSED)),
        total=Count("id"),
    )
    late_counted = counts["late"] if policy.count_late_as_present else 0
    excused_excluded = counts["excused"] if policy.exclude_excused_from_total else 0
    percentage = attendance_percentage(
        present=counts["present"],
        late=late_counted,
        excused=excused_excluded,
        total=counts["total"],
    )
    counts["percentage"] = float(percentage)
    counts["status"] = attendance_status(
        percentage, policy.warning_threshold, policy.critical_threshold
    )
    counts["warning_threshold"] = float(policy.warning_threshold)
    counts["critical_threshold"] = float(policy.critical_threshold)
    counts["sessions_to_reach_threshold"] = sessions_needed_to_reach(
        counts["present"], late_counted, counts["total"], policy.warning_threshold
    )
    return counts


def student_overall(student, section=None):
    """Overall attendance for a student, optionally scoped to one section."""
    policy = AttendancePolicy.resolve_for(student.department)
    qs = AttendanceRecord.objects.filter(student=student)
    if section is not None:
        qs = qs.filter(session__section=section)
    return summarise(qs, policy)


def student_by_course(student):
    """Per-section attendance breakdown for the student dashboard."""
    policy = AttendancePolicy.resolve_for(student.department)
    records = (
        AttendanceRecord.objects.filter(student=student)
        .select_related("session__section__course")
        .values(
            "session__section_id",
            "session__section__name",
            "session__section__course__code",
            "session__section__course__name",
            "status",
        )
        .annotate(count=Count("id"))
    )

    buckets = defaultdict(
        lambda: {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
    )
    labels = {}
    for row in records:
        key = row["session__section_id"]
        labels[key] = {
            "section_id": str(key),
            "section_name": row["session__section__name"],
            "course_code": row["session__section__course__code"],
            "course_name": row["session__section__course__name"],
        }
        bucket = buckets[key]
        bucket[row["status"].lower()] += row["count"]
        bucket["total"] += row["count"]

    results = []
    for key, bucket in buckets.items():
        late_counted = bucket["late"] if policy.count_late_as_present else 0
        excused_excluded = bucket["excused"] if policy.exclude_excused_from_total else 0
        pct = attendance_percentage(
            bucket["present"], late_counted, excused_excluded, bucket["total"]
        )
        results.append(
            {
                **labels[key],
                **bucket,
                "percentage": float(pct),
                "status": attendance_status(
                    pct, policy.warning_threshold, policy.critical_threshold
                ),
            }
        )
    return sorted(results, key=lambda item: item["course_code"])


def monthly_trend(student, months=6):
    """Month-by-month attendance percentage for the trend chart."""
    from django.db.models.functions import TruncMonth

    policy = AttendancePolicy.resolve_for(student.department)
    rows = (
        AttendanceRecord.objects.filter(student=student)
        .annotate(month=TruncMonth("session__date"))
        .values("month", "status")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    buckets = defaultdict(lambda: {"present": 0, "late": 0, "excused": 0, "total": 0})
    for row in rows:
        if row["month"] is None:
            continue
        bucket = buckets[row["month"]]
        key = row["status"].lower()
        if key in bucket:
            bucket[key] += row["count"]
        bucket["total"] += row["count"]

    trend = []
    for month in sorted(buckets)[-months:]:
        bucket = buckets[month]
        late_counted = bucket["late"] if policy.count_late_as_present else 0
        excused_excluded = bucket["excused"] if policy.exclude_excused_from_total else 0
        trend.append(
            {
                "month": month.strftime("%Y-%m"),
                "label": month.strftime("%b %Y"),
                "percentage": float(
                    attendance_percentage(
                        bucket["present"], late_counted, excused_excluded, bucket["total"]
                    )
                ),
                "sessions": bucket["total"],
            }
        )
    return trend


def consecutive_absences(student, section):
    """Length of the student's current unbroken absence streak in a section."""
    statuses = list(
        AttendanceRecord.objects.filter(student=student, session__section=section)
        .order_by("-session__date", "-session__period")
        .values_list("status", flat=True)[:20]
    )
    streak = 0
    for value in statuses:
        if value == Status.ABSENT:
            streak += 1
        else:
            break
    return streak


def evaluate_alerts(section):
    """Generate attendance alerts for a section. Returns the alerts created."""
    from apps.courses.models import Enrollment

    policy = AttendancePolicy.resolve_for(section.course.department)
    created = []
    enrollments = section.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related(
        "student"
    )
    for enrollment in enrollments:
        student = enrollment.student
        summary = student_overall(student, section=section)
        if summary["total"] == 0:
            continue

        level = None
        message = ""
        if summary["status"] == "critical":
            level = AttendanceAlert.Level.CRITICAL
            message = "Attendance in %s is %.1f%%, below the critical threshold of %s%%." % (
                section.course.code,
                summary["percentage"],
                policy.critical_threshold,
            )
        elif summary["status"] == "warning":
            level = AttendanceAlert.Level.WARNING
            message = "Attendance in %s is %.1f%%, below the required %s%%." % (
                section.course.code,
                summary["percentage"],
                policy.warning_threshold,
            )

        streak = consecutive_absences(student, section)
        if level is None and streak >= policy.consecutive_absence_alert:
            level = AttendanceAlert.Level.CONSECUTIVE
            message = "%s consecutive absences recorded in %s." % (streak, section.course.code)

        if level is None:
            continue
        # Do not re-raise an identical unacknowledged alert.
        exists = AttendanceAlert.objects.filter(
            student=student, section=section, level=level, acknowledged_at__isnull=True
        ).exists()
        if exists:
            continue
        created.append(
            AttendanceAlert.objects.create(
                student=student,
                section=section,
                level=level,
                percentage=summary["percentage"],
                message=message,
            )
        )
    return created
