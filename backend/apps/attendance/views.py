from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.attendance import services
from apps.attendance.models import (
    AttendanceAlert,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceSession,
)
from apps.attendance.serializers import (
    AttendanceAlertSerializer,
    AttendancePolicySerializer,
    AttendanceRecordSerializer,
    AttendanceSessionSerializer,
    MarkAttendanceSerializer,
)
from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm, Roles, teaches_section
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import CourseSection, Enrollment


class AttendancePolicyViewSet(AuditedModelViewSet):
    queryset = AttendancePolicy.objects.select_related("department").all()
    serializer_class = AttendancePolicySerializer
    required_permission = Perm.ATTENDANCE_VIEW_OWN
    required_write_permission = Perm.ATTENDANCE_CONFIGURE
    pagination_class = None
    audit_object_type = "attendance policy"


class AttendanceSessionViewSet(AuditedModelViewSet):
    queryset = AttendanceSession.objects.select_related(
        "section__course", "marked_by"
    ).prefetch_related("records")
    serializer_class = AttendanceSessionSerializer
    required_permission = Perm.ATTENDANCE_VIEW_ALL
    required_write_permission = Perm.ATTENDANCE_MARK
    filterset_fields = ["section", "date", "status", "session_type"]
    ordering_fields = ["date", "period"]
    audit_object_type = "attendance session"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                section__faculty_assignments__faculty=user,
                section__faculty_assignments__is_active=True,
            ).distinct()
        elif user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(section__course__department=user.department)
        elif user.role == Roles.STUDENT:
            qs = qs.filter(records__student=user).distinct()
        return qs

    def perform_create(self, serializer):
        section = serializer.validated_data["section"]
        if not teaches_section(self.request.user, section):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You are not assigned to teach this section.")
        instance = serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
            marked_by=self.request.user,
        )
        # Pre-populate a row for every active enrolment so the UI has a full roster.
        enrollments = instance.section.enrollments.filter(status=Enrollment.Status.ACTIVE)
        AttendanceRecord.objects.bulk_create(
            [
                AttendanceRecord(
                    session=instance,
                    student=enrollment.student,
                    status=AttendanceRecord.Status.PRESENT,
                    created_by=self.request.user,
                )
                for enrollment in enrollments
            ]
        )
        audit.record(
            AuditAction.CREATE, obj=instance, description="Attendance session opened"
        )
        return instance

    @action(detail=True, methods=["get"])
    def roster(self, request, pk=None):
        session = self.get_object()
        records = session.records.select_related(
            "student", "student__student_profile"
        ).order_by("student__full_name")
        return Response(
            {
                "session": AttendanceSessionSerializer(session).data,
                "records": AttendanceRecordSerializer(records, many=True).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="mark")
    def mark(self, request, pk=None):
        """Bulk-mark attendance and optionally finalise the session."""
        session = self.get_object()
        if not teaches_section(request.user, session.section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not session.is_editable:
            return Response(
                {"error": {"code": "conflict", "message": "This session is locked and cannot be edited."}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = MarkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrolled_ids = set(
            str(pk_)
            for pk_ in session.section.enrollments.filter(
                status=Enrollment.Status.ACTIVE
            ).values_list("student_id", flat=True)
        )

        updated, rejected = 0, []
        with transaction.atomic():
            for row in serializer.validated_data["records"]:
                student_id = str(row["student"])
                if student_id not in enrolled_ids:
                    rejected.append({"student": student_id, "reason": "Not enrolled in this section."})
                    continue
                AttendanceRecord.objects.update_or_create(
                    session=session,
                    student_id=student_id,
                    defaults={
                        "status": row["status"],
                        "remarks": row.get("remarks", "")[:250],
                        "updated_by": request.user,
                    },
                )
                updated += 1

            if serializer.validated_data.get("finalize"):
                session.status = AttendanceSession.Status.FINALIZED
                session.finalized_at = timezone.now()
                session.marked_by = request.user
                session.save(update_fields=["status", "finalized_at", "marked_by", "updated_at"])

        audit.record(
            AuditAction.ATTENDANCE_CHANGE,
            obj=session,
            description="Marked attendance for %s students" % updated,
            metadata={"updated": updated, "rejected": len(rejected)},
        )
        alerts = services.evaluate_alerts(session.section) if serializer.validated_data.get("finalize") else []
        return Response(
            {
                "updated": updated,
                "rejected": rejected,
                "status": session.status,
                "alerts_generated": len(alerts),
            }
        )

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        if not request.user.has_perm_code(Perm.ATTENDANCE_CONFIGURE):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot lock attendance."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        session = self.get_object()
        session.status = AttendanceSession.Status.LOCKED
        session.save(update_fields=["status", "updated_at"])
        audit.record(AuditAction.ATTENDANCE_CHANGE, obj=session, description="Attendance locked")
        return Response(AttendanceSessionSerializer(session).data)


class AttendanceRecordViewSet(AuditedModelViewSet):
    queryset = AttendanceRecord.objects.select_related(
        "student", "session__section__course"
    ).all()
    serializer_class = AttendanceRecordSerializer
    required_permission = Perm.ATTENDANCE_VIEW_OWN
    required_write_permission = Perm.ATTENDANCE_MARK
    filterset_fields = ["session", "student", "status"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.has_perm_code(Perm.ATTENDANCE_VIEW_ALL):
            qs = qs.filter(student=user)
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                session__section__faculty_assignments__faculty=user,
                session__section__faculty_assignments__is_active=True,
            ).distinct()
        return qs


class AttendanceSummaryView(AuditedModelViewSet):
    """Read-only aggregation endpoints under /api/v1/attendance/summary."""

    queryset = AttendanceRecord.objects.none()
    serializer_class = AttendanceRecordSerializer
    required_permission = Perm.ATTENDANCE_VIEW_OWN
    http_method_names = ["get"]

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        user = request.user
        return Response(
            {
                "overall": services.student_overall(user),
                "by_course": services.student_by_course(user),
                "monthly_trend": services.monthly_trend(user),
            }
        )

    @action(detail=False, methods=["get"], url_path="student/(?P<student_id>[^/.]+)")
    def student(self, request, student_id=None):
        """Another student's attendance - staff only, never student-to-student."""
        if str(request.user.pk) != str(student_id) and not request.user.has_perm_code(
            Perm.ATTENDANCE_VIEW_ALL
        ):
            audit.record(
                AuditAction.PERMISSION_DENIED,
                description="Attempted to view another student's attendance",
                metadata={"target": str(student_id)},
            )
            return Response(
                {"error": {"code": "permission_denied", "message": "You may only view your own attendance."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        target = User.objects.filter(pk=student_id).first()
        if target is None:
            return Response(
                {"error": {"code": "not_found", "message": "Student not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "student": {"id": str(target.pk), "full_name": target.full_name},
                "overall": services.student_overall(target),
                "by_course": services.student_by_course(target),
                "monthly_trend": services.monthly_trend(target),
            }
        )

    @action(detail=False, methods=["get"], url_path="section/(?P<section_id>[^/.]+)")
    def section(self, request, section_id=None):
        """Per-student attendance register for one section."""
        section = CourseSection.objects.filter(pk=section_id).select_related("course").first()
        if section is None:
            return Response(
                {"error": {"code": "not_found", "message": "Section not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not teaches_section(request.user, section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        policy = AttendancePolicy.resolve_for(section.course.department)
        rows = []
        enrollments = section.enrollments.filter(
            status=Enrollment.Status.ACTIVE
        ).select_related("student", "student__student_profile")
        for enrollment in enrollments:
            summary = services.summarise(
                AttendanceRecord.objects.filter(
                    student=enrollment.student, session__section=section
                ),
                policy,
            )
            rows.append(
                {
                    "student_id": str(enrollment.student_id),
                    "full_name": enrollment.student.full_name,
                    "enrollment_number": getattr(
                        getattr(enrollment.student, "student_profile", None),
                        "enrollment_number",
                        "",
                    ),
                    **summary,
                }
            )
        rows.sort(key=lambda item: item["percentage"])
        return Response(
            {
                "section": {
                    "id": str(section.pk),
                    "course_code": section.course.code,
                    "course_name": section.course.name,
                    "name": section.name,
                },
                "policy": AttendancePolicySerializer(policy).data,
                "total_sessions": section.attendance_sessions.count(),
                "students": rows,
            }
        )


class AttendanceAlertViewSet(AuditedModelViewSet):
    queryset = AttendanceAlert.objects.select_related("student", "section__course").all()
    serializer_class = AttendanceAlertSerializer
    required_permission = Perm.ATTENDANCE_VIEW_OWN
    required_write_permission = Perm.ATTENDANCE_MARK
    filterset_fields = ["student", "section", "level"]
    # A student may acknowledge an alert raised about their own attendance.
    action_permissions = {"acknowledge": Perm.ATTENDANCE_VIEW_OWN}

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.has_perm_code(Perm.ATTENDANCE_VIEW_ALL):
            qs = qs.filter(student=user)
        return qs

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["acknowledged_at", "updated_at"])
        return Response(AttendanceAlertSerializer(alert).data)
