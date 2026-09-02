from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.assessments import services
from apps.assessments.models import (
    AssessmentComponent,
    ComponentScore,
    CourseResult,
    ExternalMark,
    GradeBand,
    GradeScale,
)
from apps.assessments.serializers import (
    AssessmentComponentSerializer,
    BulkScoreSerializer,
    ComponentScoreSerializer,
    CourseResultSerializer,
    ExternalMarkSerializer,
    GradeBandSerializer,
    GradeScaleSerializer,
)
from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm, Roles, teaches_section
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import CourseSection


class GradeScaleViewSet(AuditedModelViewSet):
    queryset = GradeScale.objects.prefetch_related("bands").all()
    serializer_class = GradeScaleSerializer
    required_permission = Perm.MARKS_VIEW_OWN
    required_write_permission = Perm.MARKS_CONFIGURE
    pagination_class = None
    audit_object_type = "grade scale"


class GradeBandViewSet(AuditedModelViewSet):
    queryset = GradeBand.objects.select_related("scale").all()
    serializer_class = GradeBandSerializer
    required_permission = Perm.MARKS_VIEW_OWN
    required_write_permission = Perm.MARKS_CONFIGURE
    filterset_fields = ["scale"]
    pagination_class = None
    audit_object_type = "grade band"


class AssessmentComponentViewSet(AuditedModelViewSet):
    queryset = AssessmentComponent.objects.select_related("section__course").all()
    serializer_class = AssessmentComponentSerializer
    required_permission = Perm.MARKS_VIEW_OWN
    required_write_permission = Perm.MARKS_CONFIGURE
    filterset_fields = ["section", "kind", "is_active"]
    audit_object_type = "assessment component"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.STUDENT:
            qs = qs.filter(section__enrollments__student=user).distinct()
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(section__faculty_assignments__faculty=user).distinct()
        return qs

    def perform_create(self, serializer):
        section = serializer.validated_data["section"]
        if not (
            teaches_section(self.request.user, section)
            or self.request.user.has_perm_code(Perm.MARKS_CONFIGURE)
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You are not assigned to this section.")
        return super().perform_create(serializer)


class ComponentScoreViewSet(AuditedModelViewSet):
    queryset = ComponentScore.objects.select_related(
        "student", "component__section__course"
    ).all()
    serializer_class = ComponentScoreSerializer
    required_permission = Perm.MARKS_VIEW_OWN
    required_write_permission = Perm.MARKS_ENTER
    filterset_fields = ["component", "student", "status"]
    audit_object_type = "score"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.has_perm_code(Perm.MARKS_VIEW_ALL):
            # Students see only their own published marks.
            qs = qs.filter(student=user, status=ComponentScore.Status.PUBLISHED)
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                component__section__faculty_assignments__faculty=user,
                component__section__faculty_assignments__is_active=True,
            ).distinct()
        return qs

    def perform_update(self, serializer):
        instance = self.get_object()
        previous = instance.marks_obtained
        result = super().perform_update(serializer)
        audit.record(
            AuditAction.MARKS_CHANGE,
            obj=instance,
            description="Marks changed for %s" % instance.student.full_name,
            metadata={"from": str(previous), "to": str(serializer.validated_data.get("marks_obtained"))},
        )
        services.recompute_result(instance.student, instance.component.section)
        return result

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_enter(self, request):
        """Enter or update many marks for one component in a single request."""
        serializer = BulkScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        component = AssessmentComponent.objects.filter(
            pk=serializer.validated_data["component"]
        ).select_related("section__course").first()
        if component is None:
            return Response(
                {"error": {"code": "not_found", "message": "Component not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not teaches_section(request.user, component.section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        updated, rejected = 0, []
        with transaction.atomic():
            for row in serializer.validated_data["scores"]:
                student_id = row.get("student")
                marks = row.get("marks_obtained")
                existing = ComponentScore.objects.filter(
                    component=component, student_id=student_id
                ).first()
                if existing and existing.is_locked and not request.user.has_perm_code(Perm.MARKS_PUBLISH):
                    rejected.append({"student": str(student_id), "reason": "Marks are published and locked."})
                    continue
                if marks is not None:
                    try:
                        marks_value = float(marks)
                    except (TypeError, ValueError):
                        rejected.append({"student": str(student_id), "reason": "Marks must be numeric."})
                        continue
                    if marks_value < 0 or marks_value > float(component.max_marks):
                        rejected.append(
                            {
                                "student": str(student_id),
                                "reason": "Marks must be between 0 and %s." % component.max_marks,
                            }
                        )
                        continue
                ComponentScore.objects.update_or_create(
                    component=component,
                    student_id=student_id,
                    defaults={
                        "marks_obtained": marks,
                        "is_absent": bool(row.get("is_absent", False)),
                        "remarks": str(row.get("remarks", ""))[:250],
                        "updated_by": request.user,
                    },
                )
                updated += 1

        audit.record(
            AuditAction.MARKS_CHANGE,
            obj=component,
            description="Bulk mark entry: %s updated" % updated,
            metadata={"updated": updated, "rejected": len(rejected)},
        )
        services.recompute_section(component.section)
        return Response({"updated": updated, "rejected": rejected})

    @action(detail=False, methods=["post"], url_path="publish")
    def publish(self, request):
        """Move a component's marks to PUBLISHED, which locks them."""
        if not request.user.has_perm_code(Perm.MARKS_PUBLISH):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot publish marks."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        component_id = request.data.get("component")
        component = AssessmentComponent.objects.filter(pk=component_id).first()
        if component is None:
            return Response(
                {"error": {"code": "not_found", "message": "Component not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        count = ComponentScore.objects.filter(component=component).update(
            status=ComponentScore.Status.PUBLISHED,
            published_at=timezone.now(),
            published_by=request.user,
        )
        CourseResult.objects.filter(section=component.section).update(is_published=True)
        services.recompute_section(component.section)
        audit.record(
            AuditAction.MARKS_PUBLISH,
            obj=component,
            description="Published %s marks for %s" % (count, component.name),
        )
        return Response({"published": count, "component": component.name})


class ExternalMarkViewSet(AuditedModelViewSet):
    queryset = ExternalMark.objects.select_related("student", "section__course").all()
    serializer_class = ExternalMarkSerializer
    required_permission = Perm.MARKS_VIEW_OWN
    required_write_permission = Perm.EXTERNAL_MARKS_ENTER
    filterset_fields = ["student", "section", "kind", "status"]
    audit_object_type = "external mark"

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.has_perm_code(Perm.MARKS_VIEW_ALL):
            qs = qs.filter(student=self.request.user, status=ExternalMark.Status.PUBLISHED)
        return qs

    def perform_create(self, serializer):
        instance = super().perform_create(serializer)
        services.recompute_result(instance.student, instance.section)
        return instance


class GradebookViewSet(AuditedModelViewSet):
    """Read endpoints under /api/v1/gradebook."""

    queryset = CourseResult.objects.none()
    serializer_class = CourseResultSerializer
    required_permission = Perm.MARKS_VIEW_OWN
    http_method_names = ["get", "post"]

    @action(detail=False, methods=["get"], url_path="section/(?P<section_id>[^/.]+)")
    def section(self, request, section_id=None):
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
        return Response(services.gradebook(section))

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        """A student's own marks - published components only."""
        user = request.user
        published = (
            ComponentScore.objects.filter(student=user, status=ComponentScore.Status.PUBLISHED)
            .select_related("component__section__course")
            .order_by("component__section__course__code", "component__display_order")
        )
        by_course = {}
        for score in published:
            section = score.component.section
            key = str(section.id)
            by_course.setdefault(
                key,
                {
                    "section_id": key,
                    "course_code": section.course.code,
                    "course_name": section.course.name,
                    "credits": float(section.course.credits),
                    "components": [],
                },
            )
            by_course[key]["components"].append(
                {
                    "name": score.component.name,
                    "kind": score.component.kind,
                    "marks_obtained": float(score.marks_obtained)
                    if score.marks_obtained is not None
                    else None,
                    "max_marks": float(score.component.max_marks),
                    "weight": float(score.component.weight),
                    "is_absent": score.is_absent,
                    "remarks": score.remarks,
                }
            )

        results = CourseResult.objects.filter(student=user, is_published=True).select_related(
            "section__course"
        )
        for result in results:
            key = str(result.section_id)
            if key in by_course:
                by_course[key].update(
                    {
                        "total_marks": float(result.total_marks),
                        "percentage": float(result.percentage),
                        "grade_letter": result.grade_letter,
                        "grade_point": float(result.grade_point),
                        "is_pass": result.is_pass,
                    }
                )

        return Response(
            {
                "courses": list(by_course.values()),
                "transcript": services.student_transcript(user),
            }
        )

    @action(detail=False, methods=["get"], url_path="student/(?P<student_id>[^/.]+)")
    def student(self, request, student_id=None):
        if str(request.user.pk) != str(student_id) and not request.user.has_perm_code(
            Perm.MARKS_VIEW_ALL
        ):
            audit.record(
                AuditAction.PERMISSION_DENIED,
                description="Attempted to view another student's marks",
                metadata={"target": str(student_id)},
            )
            return Response(
                {"error": {"code": "permission_denied", "message": "You may only view your own marks."}},
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
                "transcript": services.student_transcript(target),
            }
        )

    @action(detail=False, methods=["post"], url_path="recompute")
    def recompute(self, request):
        if not request.user.has_perm_code(Perm.MARKS_ENTER):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot recompute results."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        section = CourseSection.objects.filter(pk=request.data.get("section")).first()
        if section is None:
            return Response(
                {"error": {"code": "not_found", "message": "Section not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        results = services.recompute_section(section)
        return Response({"recomputed": len(results)})
