from django.db.models import Count, Q
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.academics.models import (
    AcademicSession,
    Batch,
    CurriculumItem,
    Department,
    Holiday,
    Program,
    Semester,
)
from apps.academics.serializers import (
    AcademicSessionSerializer,
    BatchSerializer,
    CurriculumItemSerializer,
    DepartmentSerializer,
    HolidaySerializer,
    ProgramSerializer,
    SemesterSerializer,
)
from apps.core.permissions import Perm, Roles
from apps.core.viewsets import AuditedModelViewSet


class DepartmentViewSet(AuditedModelViewSet):
    queryset = Department.objects.select_related("hod").all()
    serializer_class = DepartmentSerializer
    required_permission = Perm.DEPARTMENT_VIEW
    required_write_permission = Perm.DEPARTMENT_MANAGE
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    audit_object_type = "department"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                program_count=Count("programs", distinct=True),
                member_count=Count("members", distinct=True),
            )
        )


class ProgramViewSet(AuditedModelViewSet):
    queryset = Program.objects.select_related("department").all()
    serializer_class = ProgramSerializer
    required_permission = Perm.DEPARTMENT_VIEW
    required_write_permission = Perm.ACADEMIC_MANAGE
    filterset_fields = ["department", "level", "is_active"]
    search_fields = ["name", "code"]
    audit_object_type = "program"

    def get_queryset(self):
        qs = super().get_queryset().annotate(student_count=Count("students", distinct=True))
        user = self.request.user
        if user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(department=user.department)
        return qs


class AcademicSessionViewSet(AuditedModelViewSet):
    queryset = AcademicSession.objects.all()
    serializer_class = AcademicSessionSerializer
    required_permission = Perm.DEPARTMENT_VIEW
    required_write_permission = Perm.ACADEMIC_MANAGE
    filterset_fields = ["is_current", "is_active"]
    audit_object_type = "academic session"

    def get_queryset(self):
        return super().get_queryset().annotate(semester_count=Count("semesters", distinct=True))

    @action(detail=False, methods=["get"])
    def current(self, request):
        session = AcademicSession.objects.filter(is_current=True).first()
        if session is None:
            return Response(None)
        return Response(AcademicSessionSerializer(session).data)


class SemesterViewSet(AuditedModelViewSet):
    queryset = Semester.objects.select_related("session").all()
    serializer_class = SemesterSerializer
    required_permission = Perm.DEPARTMENT_VIEW
    required_write_permission = Perm.ACADEMIC_MANAGE
    filterset_fields = ["session", "is_current", "number"]
    audit_object_type = "semester"

    @action(detail=False, methods=["get"])
    def current(self, request):
        semester = Semester.objects.filter(is_current=True).select_related("session").first()
        if semester is None:
            return Response(None)
        return Response(SemesterSerializer(semester).data)


class BatchViewSet(AuditedModelViewSet):
    queryset = Batch.objects.select_related("program").all()
    serializer_class = BatchSerializer
    required_permission = Perm.DEPARTMENT_VIEW
    required_write_permission = Perm.ACADEMIC_MANAGE
    filterset_fields = ["program", "is_active", "start_year"]
    search_fields = ["name"]
    audit_object_type = "batch"

    def get_queryset(self):
        return super().get_queryset().annotate(student_count=Count("students", distinct=True))


class CurriculumItemViewSet(AuditedModelViewSet):
    queryset = CurriculumItem.objects.select_related("program", "course", "batch").all()
    serializer_class = CurriculumItemSerializer
    required_permission = Perm.COURSE_VIEW
    required_write_permission = Perm.ACADEMIC_MANAGE
    filterset_fields = ["program", "batch", "semester_number", "category"]
    audit_object_type = "curriculum item"

    @action(detail=False, methods=["get"], url_path="by-program")
    def by_program(self, request):
        """Curriculum grouped by semester, for the curriculum manager screen."""
        program_id = request.query_params.get("program")
        if not program_id:
            return Response({"error": {"code": "validation_error", "message": "A program id is required."}}, status=400)
        items = self.get_queryset().filter(program_id=program_id).order_by(
            "semester_number", "display_order"
        )
        grouped = {}
        for item in items:
            grouped.setdefault(item.semester_number, []).append(
                CurriculumItemSerializer(item).data
            )
        return Response(
            {
                "program": program_id,
                "semesters": [
                    {
                        "semester_number": number,
                        "courses": courses,
                        "total_credits": sum(float(c["credits"]) for c in courses),
                    }
                    for number, courses in sorted(grouped.items())
                ],
            }
        )


class HolidayViewSet(AuditedModelViewSet):
    queryset = Holiday.objects.select_related("session").all()
    serializer_class = HolidaySerializer
    required_permission = Perm.EVENT_VIEW
    required_write_permission = Perm.ACADEMIC_MANAGE
    filterset_fields = ["session"]
    audit_object_type = "holiday"
