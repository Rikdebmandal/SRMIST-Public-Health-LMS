"""Analytics: role dashboards and the Academic Support Risk Indicator."""
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.analytics.models import ActivityLog, RiskRule, RiskSnapshot
from apps.attendance import services as attendance_services
from apps.core.calculations import DEFAULT_RISK_RULES, evaluate_risk, linear_trend
from apps.core.rbac import Roles


def active_rules(department=None):
    """Configured rules when present, otherwise the documented defaults."""
    qs = RiskRule.objects.filter(is_active=True)
    if department is not None:
        scoped = qs.filter(department=department)
        if scoped.exists():
            return [rule.as_dict() for rule in scoped]
    generic = qs.filter(department__isnull=True)
    if generic.exists():
        return [rule.as_dict() for rule in generic]
    return DEFAULT_RISK_RULES


def collect_metrics(student):
    """Gather the observable metrics the risk rules are evaluated against."""
    from apps.assessments.models import ComponentScore
    from apps.assignments.models import Assignment, AssignmentSubmission
    from apps.courses.models import Enrollment

    attendance = attendance_services.student_overall(student)

    scores = list(
        ComponentScore.objects.filter(
            student=student, marks_obtained__isnull=False
        )
        .select_related("component")
        .order_by("created_at")
    )
    percentages = [
        float(score.marks_obtained) / float(score.component.max_marks) * 100
        for score in scores
        if score.component.max_marks
    ]
    average = sum(percentages) / len(percentages) if percentages else None
    failed = sum(1 for value in percentages if value < 40)

    section_ids = list(
        Enrollment.objects.filter(student=student, status=Enrollment.Status.ACTIVE).values_list(
            "section_id", flat=True
        )
    )
    due_assignments = Assignment.objects.filter(
        section_id__in=section_ids,
        status=Assignment.Status.PUBLISHED,
        due_date__lt=timezone.now(),
    )
    submitted = set(
        AssignmentSubmission.objects.filter(
            student=student, assignment__in=due_assignments
        ).values_list("assignment_id", flat=True)
    )
    missed = due_assignments.exclude(id__in=submitted).count()

    last_activity = (
        ActivityLog.objects.filter(user=student).order_by("-created_at").values_list("created_at", flat=True).first()
    )
    reference = last_activity or student.last_active_at
    days_inactive = (timezone.now() - reference).days if reference else 999

    return {
        "attendance_percentage": attendance["percentage"],
        "average_percentage": average,
        "missed_assignments": missed,
        "score_trend": float(linear_trend(percentages)) if len(percentages) >= 2 else 0,
        "days_inactive": days_inactive,
        "failed_assessments": failed,
        "assessments_recorded": len(percentages),
        "attendance_sessions": attendance["total"],
    }


def evaluate_student_risk(student, persist=False):
    """Run the risk rules for one student and optionally store a snapshot."""
    metrics = collect_metrics(student)
    rules = active_rules(student.department)
    outcome = evaluate_risk(metrics, rules)
    outcome["metrics"] = metrics
    outcome["student"] = {
        "id": str(student.pk),
        "full_name": student.full_name,
        "enrollment_number": getattr(
            getattr(student, "student_profile", None), "enrollment_number", ""
        ),
    }
    if persist:
        RiskSnapshot.objects.create(
            student=student,
            score=outcome["score"],
            level=outcome["level"],
            factors=outcome["factors"],
            metrics=metrics,
        )
    return outcome


def at_risk_students(department=None, limit=50, minimum_level="moderate"):
    """Rank students by risk score for the staff dashboards."""
    from apps.accounts.models import User

    order = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
    floor = order.get(minimum_level, 1)

    students = User.objects.filter(role=Roles.STUDENT, is_active=True).select_related(
        "student_profile", "department"
    )
    if department is not None:
        students = students.filter(department=department)

    results = []
    for student in students[:300]:  # bounded scan keeps the endpoint responsive
        outcome = evaluate_student_risk(student)
        if order.get(outcome["level"], 0) >= floor:
            results.append(outcome)
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------
def student_dashboard(user):
    from apps.announcements.models import Announcement
    from apps.assessments.models import ComponentScore
    from apps.assessments.services import student_transcript
    from apps.assignments.models import Assignment, AssignmentSubmission
    from apps.calendarapp.models import CalendarEvent
    from apps.courses.models import Enrollment

    sections = Enrollment.objects.filter(
        student=user, status=Enrollment.Status.ACTIVE
    ).select_related("section__course", "section__semester")
    section_ids = [enrollment.section_id for enrollment in sections]

    submitted = set(
        AssignmentSubmission.objects.filter(student=user).values_list("assignment_id", flat=True)
    )
    upcoming = (
        Assignment.objects.filter(
            section_id__in=section_ids,
            status=Assignment.Status.PUBLISHED,
            due_date__gte=timezone.now(),
        )
        .exclude(id__in=submitted)
        .select_related("section__course")
        .order_by("due_date")[:5]
    )
    pending_count = (
        Assignment.objects.filter(
            section_id__in=section_ids, status=Assignment.Status.PUBLISHED, due_date__gte=timezone.now()
        )
        .exclude(id__in=submitted)
        .count()
    )

    recent_marks = (
        ComponentScore.objects.filter(student=user, status=ComponentScore.Status.PUBLISHED)
        .select_related("component__section__course")
        .order_by("-published_at")[:5]
    )

    announcements = [
        item
        for item in Announcement.objects.filter(status=Announcement.Status.PUBLISHED).order_by(
            "-is_pinned", "-publish_at"
        )[:20]
        if item.visible_to(user)
    ][:5]

    events = CalendarEvent.objects.filter(
        is_published=True, start_at__gte=timezone.now()
    ).order_by("start_at")[:5]

    attendance = attendance_services.student_overall(user)
    transcript = student_transcript(user)
    risk = evaluate_student_risk(user)

    return {
        "profile": {
            "full_name": user.full_name,
            "role": user.role,
            "department": user.department.name if user.department else "",
            "enrollment_number": getattr(
                getattr(user, "student_profile", None), "enrollment_number", ""
            ),
            "current_semester": getattr(
                getattr(user, "student_profile", None), "current_semester", None
            ),
        },
        "kpis": {
            "attendance_percentage": attendance["percentage"],
            "attendance_status": attendance["status"],
            "cgpa": transcript["cgpa"],
            "enrolled_courses": len(section_ids),
            "pending_assignments": pending_count,
            "credits_earned": transcript["total_credits"],
        },
        "courses": [
            {
                "section_id": str(enrollment.section_id),
                "code": enrollment.section.course.code,
                "name": enrollment.section.course.name,
                "credits": float(enrollment.section.course.credits),
                "section": enrollment.section.name,
            }
            for enrollment in sections
        ],
        "upcoming_assignments": [
            {
                "id": str(item.id),
                "title": item.title,
                "course": item.section.course.code,
                "due_date": item.due_date.isoformat(),
                "max_marks": float(item.max_marks),
            }
            for item in upcoming
        ],
        "recent_marks": [
            {
                "component": score.component.name,
                "course": score.component.section.course.code,
                "marks": float(score.marks_obtained) if score.marks_obtained is not None else None,
                "max_marks": float(score.component.max_marks),
                "published_at": score.published_at.isoformat() if score.published_at else None,
            }
            for score in recent_marks
        ],
        "announcements": [
            {
                "id": str(item.id),
                "title": item.title,
                "priority": item.priority,
                "publish_at": item.publish_at.isoformat(),
            }
            for item in announcements
        ],
        "events": [
            {
                "id": str(event.id),
                "title": event.title,
                "category": event.category,
                "start_at": event.start_at.isoformat(),
            }
            for event in events
        ],
        "attendance_by_course": attendance_services.student_by_course(user),
        "attendance_trend": attendance_services.monthly_trend(user),
        "risk": risk,
    }


def faculty_dashboard(user):
    from apps.assignments.models import Assignment, AssignmentSubmission
    from apps.attendance.models import AttendancePolicy, AttendanceRecord, AttendanceSession
    from apps.courses.models import CourseSection, Enrollment

    sections = (
        CourseSection.objects.filter(
            faculty_assignments__faculty=user, faculty_assignments__is_active=True
        )
        .select_related("course", "semester")
        .distinct()
    )
    section_ids = [section.id for section in sections]

    total_students = (
        Enrollment.objects.filter(
            section_id__in=section_ids, status=Enrollment.Status.ACTIVE
        )
        .values("student_id")
        .distinct()
        .count()
    )
    pending_grading = AssignmentSubmission.objects.filter(
        assignment__section_id__in=section_ids,
        status__in=[AssignmentSubmission.Status.SUBMITTED, AssignmentSubmission.Status.LATE],
    ).count()
    recent_submissions = (
        AssignmentSubmission.objects.filter(assignment__section_id__in=section_ids)
        .select_related("student", "assignment__section__course")
        .order_by("-submitted_at")[:8]
    )
    today = timezone.localdate()
    todays_sessions = AttendanceSession.objects.filter(
        section_id__in=section_ids, date=today
    ).select_related("section__course")

    course_stats = []
    for section in sections:
        summary = attendance_services.summarise(
            AttendanceRecord.objects.filter(session__section=section),
            AttendancePolicy.resolve_for(section.course.department),
        )
        course_stats.append(
            {
                "section_id": str(section.id),
                "code": section.course.code,
                "name": section.course.name,
                "section": section.name,
                "students": section.enrollments.filter(status=Enrollment.Status.ACTIVE).count(),
                "attendance_percentage": summary["percentage"],
                "sessions_held": section.attendance_sessions.count(),
            }
        )

    return {
        "kpis": {
            "assigned_sections": len(section_ids),
            "total_students": total_students,
            "pending_grading": pending_grading,
            "sessions_today": todays_sessions.count(),
            "open_assignments": Assignment.objects.filter(
                section_id__in=section_ids,
                status=Assignment.Status.PUBLISHED,
                due_date__gte=timezone.now(),
            ).count(),
        },
        "sections": course_stats,
        "todays_classes": [
            {
                "id": str(item.id),
                "course": item.section.course.code,
                "period": item.period,
                "status": item.status,
                "topic": item.topic,
            }
            for item in todays_sessions
        ],
        "recent_submissions": [
            {
                "id": str(item.id),
                "student": item.student.full_name,
                "assignment": item.assignment.title,
                "course": item.assignment.section.course.code,
                "submitted_at": item.submitted_at.isoformat(),
                "status": item.status,
            }
            for item in recent_submissions
        ],
        "at_risk": at_risk_students(department=user.department, limit=8, minimum_level="high"),
    }


def department_dashboard(department):
    from apps.accounts.models import User
    from apps.assessments.models import CourseResult
    from apps.attendance.models import AttendancePolicy, AttendanceRecord
    from apps.courses.models import Course, CourseSection

    students = User.objects.filter(role=Roles.STUDENT, department=department, is_active=True)
    faculty = User.objects.filter(role=Roles.FACULTY, department=department, is_active=True)
    scholars = User.objects.filter(role=Roles.SCHOLAR, department=department, is_active=True)
    courses = Course.objects.filter(department=department)

    policy = AttendancePolicy.resolve_for(department)
    attendance = attendance_services.summarise(
        AttendanceRecord.objects.filter(session__section__course__department=department), policy
    )

    performance = CourseResult.objects.filter(
        section__course__department=department
    ).aggregate(average=Avg("percentage"), count=Count("id"))

    course_performance = list(
        CourseResult.objects.filter(section__course__department=department)
        .values("section__course__code", "section__course__name")
        .annotate(average=Avg("percentage"), students=Count("id"))
        .order_by("-average")[:10]
    )

    faculty_workload = list(
        CourseSection.objects.filter(course__department=department, is_active=True)
        .values("faculty_assignments__faculty__full_name")
        .annotate(sections=Count("id", distinct=True))
        .order_by("-sections")[:10]
    )

    return {
        "department": {"id": str(department.id), "name": department.name, "code": department.code},
        "kpis": {
            "students": students.count(),
            "faculty": faculty.count(),
            "scholars": scholars.count(),
            "courses": courses.count(),
            "average_attendance": attendance["percentage"],
            "average_performance": round(float(performance["average"] or 0), 2),
        },
        "course_performance": [
            {
                "code": row["section__course__code"],
                "name": row["section__course__name"],
                "average": round(float(row["average"] or 0), 2),
                "students": row["students"],
            }
            for row in course_performance
        ],
        "faculty_workload": [
            {
                "faculty": row["faculty_assignments__faculty__full_name"] or "Unassigned",
                "sections": row["sections"],
            }
            for row in faculty_workload
        ],
        "at_risk": at_risk_students(department=department, limit=15),
        "attendance_distribution": attendance,
    }


def institution_dashboard():
    from apps.academics.models import Department
    from apps.accounts.models import User
    from apps.assessments.models import CourseResult
    from apps.attendance.models import AttendancePolicy, AttendanceRecord
    from apps.courses.models import Course

    policy = AttendancePolicy.resolve_for(None)
    attendance = attendance_services.summarise(AttendanceRecord.objects.all(), policy)

    departments = []
    for department in Department.objects.filter(is_active=True):
        dept_attendance = attendance_services.summarise(
            AttendanceRecord.objects.filter(session__section__course__department=department),
            AttendancePolicy.resolve_for(department),
        )
        dept_performance = CourseResult.objects.filter(
            section__course__department=department
        ).aggregate(average=Avg("percentage"))
        departments.append(
            {
                "id": str(department.id),
                "name": department.name,
                "code": department.code,
                "students": User.objects.filter(
                    role=Roles.STUDENT, department=department, is_active=True
                ).count(),
                "faculty": User.objects.filter(
                    role=Roles.FACULTY, department=department, is_active=True
                ).count(),
                "courses": Course.objects.filter(department=department).count(),
                "attendance": dept_attendance["percentage"],
                "performance": round(float(dept_performance["average"] or 0), 2),
            }
        )

    risk_counts = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for outcome in at_risk_students(limit=200, minimum_level="low"):
        risk_counts[outcome["level"]] = risk_counts.get(outcome["level"], 0) + 1

    return {
        "kpis": {
            "students": User.objects.filter(role=Roles.STUDENT, is_active=True).count(),
            "faculty": User.objects.filter(role=Roles.FACULTY, is_active=True).count(),
            "scholars": User.objects.filter(role=Roles.SCHOLAR, is_active=True).count(),
            "alumni": User.objects.filter(role=Roles.ALUMNI, is_active=True).count(),
            "courses": Course.objects.filter(status=Course.Status.ACTIVE).count(),
            "departments": Department.objects.filter(is_active=True).count(),
            "average_attendance": attendance["percentage"],
        },
        "departments": departments,
        "risk_distribution": risk_counts,
        "attendance_overview": attendance,
    }


def correlation_workspace(department=None):
    """Attendance-versus-performance scatter data for the analytics workspace."""
    from apps.accounts.models import User
    from apps.assessments.models import CourseResult

    students = User.objects.filter(role=Roles.STUDENT, is_active=True)
    if department is not None:
        students = students.filter(department=department)

    points = []
    for student in students[:200]:
        attendance = attendance_services.student_overall(student)
        if attendance["total"] == 0:
            continue
        result = CourseResult.objects.filter(student=student).aggregate(average=Avg("percentage"))
        average = float(result["average"] or 0)
        if average == 0:
            continue
        points.append(
            {
                "student_id": str(student.pk),
                "label": getattr(
                    getattr(student, "student_profile", None), "enrollment_number", ""
                )
                or student.initials,
                "attendance": attendance["percentage"],
                "performance": round(average, 2),
            }
        )
    return points
