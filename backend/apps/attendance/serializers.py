from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.attendance.models import (
    AttendanceAlert,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceSession,
)


class AttendancePolicySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default="Institution-wide")

    class Meta:
        model = AttendancePolicy
        fields = [
            "id", "name", "department", "department_name", "warning_threshold",
            "critical_threshold", "consecutive_absence_alert", "count_late_as_present",
            "exclude_excused_from_total", "is_active",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        warning = attrs.get("warning_threshold", getattr(self.instance, "warning_threshold", None))
        critical = attrs.get("critical_threshold", getattr(self.instance, "critical_threshold", None))
        if warning is not None and critical is not None and critical > warning:
            raise serializers.ValidationError(
                {"critical_threshold": "The critical threshold must be at or below the warning threshold."}
            )
        return attrs


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    enrollment_number = serializers.CharField(
        source="student.student_profile.enrollment_number", read_only=True, default=""
    )

    class Meta:
        model = AttendanceRecord
        fields = [
            "id", "session", "student", "student_detail", "enrollment_number", "status",
            "remarks", "marked_at",
        ]
        read_only_fields = ["id", "marked_at"]


class AttendanceSessionSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="section.course.code", read_only=True)
    course_name = serializers.CharField(source="section.course.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    marked_by_name = serializers.CharField(source="marked_by.full_name", read_only=True, default="")
    record_summary = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "section", "course_code", "course_name", "section_name", "date", "period",
            "session_type", "topic", "duration_minutes", "status", "marked_by",
            "marked_by_name", "finalized_at", "record_summary",
        ]
        read_only_fields = ["id", "finalized_at", "marked_by"]

    def get_record_summary(self, obj):
        summary = {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
        for record in obj.records.all():
            summary[record.status.lower()] += 1
            summary["total"] += 1
        return summary

    def validate(self, attrs):
        section = attrs.get("section", getattr(self.instance, "section", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        period = attrs.get("period", getattr(self.instance, "period", None))
        if section and date and period:
            duplicate = AttendanceSession.objects.filter(
                section=section, date=date, period=period
            )
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    "Attendance has already been created for this section, date and period."
                )
        if date and section and date < section.semester.start_date:
            raise serializers.ValidationError(
                {"date": "The date precedes the start of the semester."}
            )
        return attrs


class MarkAttendanceSerializer(serializers.Serializer):
    """Bulk marking payload: one row per student."""

    records = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    finalize = serializers.BooleanField(default=False)

    def validate_records(self, value):
        valid_statuses = {choice[0] for choice in AttendanceRecord.Status.choices}
        for row in value:
            if "student" not in row:
                raise serializers.ValidationError("Each record requires a 'student' id.")
            if row.get("status") not in valid_statuses:
                raise serializers.ValidationError(
                    "Invalid status '%s'. Allowed: %s"
                    % (row.get("status"), ", ".join(sorted(valid_statuses)))
                )
        return value


class AttendanceAlertSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    course_code = serializers.CharField(source="section.course.code", read_only=True, default="")

    class Meta:
        model = AttendanceAlert
        fields = [
            "id", "student", "student_detail", "section", "course_code", "level", "percentage",
            "message", "acknowledged_at", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
