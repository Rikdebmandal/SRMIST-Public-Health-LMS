from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm, Roles, teaches_section
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import (
    Course,
    CourseSection,
    CourseType,
    Enrollment,
    FacultyCourseAssignment,
)
from apps.courses.serializers import (
    BulkEnrollSerializer,
    CourseSectionSerializer,
    CourseSerializer,
    CourseTypeSerializer,
    EnrollmentSerializer,
    FacultyAssignmentSerializer,
)


class CourseTypeViewSet(AuditedModelViewSet):
    queryset = CourseType.objects.all()
    serializer_class = CourseTypeSerializer
    required_permission = Perm.COURSE_VIEW
    required_write_permission = Perm.COURSE_MANAGE
    pagination_class = None
    audit_object_type = "course type"


class CourseViewSet(AuditedModelViewSet):
    queryset = Course.objects.select_related(
        "department", "program", "course_type", "coordinator"
    ).all()
    serializer_class = CourseSerializer
    required_permission = Perm.COURSE_VIEW
    required_write_permission = Perm.COURSE_MANAGE
    filterset_fields = ["department", "program", "semester_number", "course_type", "status"]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["code", "name", "semester_number", "credits"]
    audit_object_type = "course"

    def get_queryset(self):
        qs = super().get_queryset().annotate(section_count=Count("sections", distinct=True))
        user = self.request.user
        if user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(department=user.department)
        elif user.role == Roles.STUDENT:
            # Students only ever see courses they are enrolled in.
            qs = qs.filter(sections__enrollments__student=user).distinct()
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                Q(sections__faculty_assignments__faculty=user) | Q(coordinator=user)
                | Q(department=user.department)
            ).distinct()
        return qs

    @action(detail=True, methods=["get"])
    def sections(self, request, pk=None):
        course = self.get_object()
        sections = course.sections.select_related("semester", "batch").all()
        return Response(CourseSectionSerializer(sections, many=True).data)

    @action(detail=False, methods=["get"], url_path="my-courses")
    def my_courses(self, request):
        """Every course the caller is connected to, whichever role they hold."""
        user = request.user
        if user.role == Roles.STUDENT:
            sections = (
                CourseSection.objects.filter(
                    enrollments__student=user, enrollments__status=Enrollment.Status.ACTIVE
                )
                .select_related("course", "semester", "batch")
                .distinct()
            )
        else:
            sections = (
                CourseSection.objects.filter(
                    faculty_assignments__faculty=user, faculty_assignments__is_active=True
                )
                .select_related("course", "semester", "batch")
                .distinct()
            )
        return Response(CourseSectionSerializer(sections, many=True).data)


class CourseSectionViewSet(AuditedModelViewSet):
    queryset = CourseSection.objects.select_related(
        "course", "course__department", "semester", "semester__session", "batch"
    ).prefetch_related("faculty_assignments__faculty")
    serializer_class = CourseSectionSerializer
    required_permission = Perm.COURSE_VIEW
    required_write_permission = Perm.COURSE_MANAGE
    filterset_fields = ["course", "semester", "batch", "is_active"]
    search_fields = ["course__code", "course__name", "name"]
    audit_object_type = "course section"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.STUDENT:
            qs = qs.filter(enrollments__student=user).distinct()
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                Q(faculty_assignments__faculty=user) | Q(course__department=user.department)
            ).distinct()
        elif user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(course__department=user.department)
        return qs

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        """Roster - restricted to staff who actually teach the section."""
        section = self.get_object()
        if not teaches_section(request.user, section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        enrollments = (
            section.enrollments.filter(status=Enrollment.Status.ACTIVE)
            .select_related("student", "student__student_profile")
            .order_by("student__full_name")
        )
        return Response(EnrollmentSerializer(enrollments, many=True).data)


class FacultyAssignmentViewSet(AuditedModelViewSet):
    queryset = FacultyCourseAssignment.objects.select_related("faculty", "section__course").all()
    serializer_class = FacultyAssignmentSerializer
    required_permission = Perm.COURSE_VIEW
    required_write_permission = Perm.COURSE_MANAGE
    filterset_fields = ["section", "faculty", "is_active"]
    audit_object_type = "faculty assignment"


class EnrollmentViewSet(AuditedModelViewSet):
    queryset = Enrollment.objects.select_related(
        "student", "student__student_profile", "section__course"
    ).all()
    serializer_class = EnrollmentSerializer
    required_permission = Perm.COURSE_VIEW
    required_write_permission = Perm.ENROLLMENT_MANAGE
    filterset_fields = ["section", "student", "status"]
    search_fields = ["student__full_name", "student__student_profile__enrollment_number"]
    audit_object_type = "enrolment"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.STUDENT:
            qs = qs.filter(student=user)
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                section__faculty_assignments__faculty=user,
                section__faculty_assignments__is_active=True,
            ).distinct()
        elif user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(section__course__department=user.department)
        return qs

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_enroll(self, request):
        """Enrol many students at once, reporting per-row outcomes."""
        if not request.user.has_perm_code(Perm.ENROLLMENT_MANAGE):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot manage enrolments."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BulkEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = CourseSection.objects.filter(pk=serializer.validated_data["section"]).first()
        if section is None:
            return Response(
                {"error": {"code": "not_found", "message": "Section not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        created, skipped = [], []
        capacity_left = section.capacity - section.enrollments.filter(
            status=Enrollment.Status.ACTIVE
        ).count()
        with transaction.atomic():
            for student_id in serializer.validated_data["students"]:
                student = User.objects.filter(pk=student_id, role=Roles.STUDENT).first()
                if student is None:
                    skipped.append({"student": str(student_id), "reason": "Not a student account."})
                    continue
                if Enrollment.objects.filter(student=student, section=section).exists():
                    skipped.append({"student": str(student_id), "reason": "Already enrolled."})
                    continue
                if capacity_left <= 0:
                    skipped.append({"student": str(student_id), "reason": "Section is full."})
                    continue
                Enrollment.objects.create(
                    student=student, section=section, created_by=request.user
                )
                capacity_left -= 1
                created.append(str(student_id))

        audit.record(
            AuditAction.CREATE,
            obj=section,
            description="Bulk enrolment: %s added, %s skipped" % (len(created), len(skipped)),
            metadata={"created": len(created), "skipped": len(skipped)},
        )
        return Response(
            {"enrolled": created, "skipped": skipped, "enrolled_count": len(created)},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
