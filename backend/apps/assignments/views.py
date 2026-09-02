from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.assignments.models import Assignment, AssignmentSubmission
from apps.assignments.serializers import (
    AssignmentSerializer,
    AssignmentSubmissionSerializer,
    GradeSubmissionSerializer,
)
from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm, Roles, teaches_section
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Enrollment
from apps.notifications.services import notify


class AssignmentViewSet(AuditedModelViewSet):
    queryset = Assignment.objects.select_related("section__course").prefetch_related("submissions")
    serializer_class = AssignmentSerializer
    required_permission = Perm.ASSIGNMENT_VIEW
    required_write_permission = Perm.ASSIGNMENT_MANAGE
    filterset_fields = ["section", "status"]
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "created_at"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    audit_object_type = "assignment"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.STUDENT:
            qs = qs.filter(
                section__enrollments__student=user,
                section__enrollments__status=Enrollment.Status.ACTIVE,
                status=Assignment.Status.PUBLISHED,
            ).distinct()
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                section__faculty_assignments__faculty=user,
                section__faculty_assignments__is_active=True,
            ).distinct()
        elif user.role == Roles.ADMIN and user.department_id:
            qs = qs.filter(section__course__department=user.department)
        return qs

    def perform_create(self, serializer):
        section = serializer.validated_data["section"]
        if not teaches_section(self.request.user, section):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You are not assigned to this section.")
        return super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        assignment = self.get_object()
        assignment.status = Assignment.Status.PUBLISHED
        assignment.published_at = timezone.now()
        assignment.save(update_fields=["status", "published_at", "updated_at"])
        audit.record(AuditAction.UPDATE, obj=assignment, description="Assignment published")

        recipients = [
            enrollment.student
            for enrollment in assignment.section.enrollments.filter(
                status=Enrollment.Status.ACTIVE
            ).select_related("student")
        ]
        notify(
            recipients,
            event="NEW_ASSIGNMENT",
            title="New assignment: %s" % assignment.title,
            body="%s - due %s"
            % (assignment.section.course.code, timezone.localtime(assignment.due_date).strftime("%d %b %Y, %H:%M")),
            link="/assignments/%s" % assignment.id,
        )
        return Response(AssignmentSerializer(assignment, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        if not teaches_section(request.user, assignment.section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        submissions = assignment.submissions.select_related(
            "student", "student__student_profile"
        ).order_by("student__full_name")
        enrolled = assignment.section.enrollments.filter(
            status=Enrollment.Status.ACTIVE
        ).select_related("student", "student__student_profile")
        submitted_ids = {str(item.student_id) for item in submissions}
        pending = [
            {
                "student_id": str(enrollment.student_id),
                "full_name": enrollment.student.full_name,
                "enrollment_number": getattr(
                    getattr(enrollment.student, "student_profile", None), "enrollment_number", ""
                ),
            }
            for enrollment in enrolled
            if str(enrollment.student_id) not in submitted_ids
        ]
        return Response(
            {
                "submissions": AssignmentSubmissionSerializer(submissions, many=True).data,
                "pending": pending,
            }
        )


class AssignmentSubmissionViewSet(AuditedModelViewSet):
    queryset = AssignmentSubmission.objects.select_related(
        "student", "assignment__section__course"
    ).all()
    serializer_class = AssignmentSubmissionSerializer
    required_permission = Perm.ASSIGNMENT_VIEW
    required_write_permission = Perm.ASSIGNMENT_SUBMIT
    filterset_fields = ["assignment", "student", "status"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    audit_object_type = "submission"
    # Students create submissions; markers grade them.
    action_permissions = {"grade": Perm.ASSIGNMENT_GRADE}

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.STUDENT:
            qs = qs.filter(student=user)
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            qs = qs.filter(
                assignment__section__faculty_assignments__faculty=user,
                assignment__section__faculty_assignments__is_active=True,
            ).distinct()
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        assignment = serializer.validated_data["assignment"]
        from rest_framework.exceptions import PermissionDenied, ValidationError

        enrolled = assignment.section.enrollments.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).exists()
        if not enrolled:
            raise PermissionDenied("You are not enrolled in this course.")
        if assignment.status != Assignment.Status.PUBLISHED:
            raise ValidationError("This assignment is not open for submission.")

        now = timezone.now()
        late = now > assignment.due_date
        if late and not assignment.allow_late_submission:
            raise ValidationError("The deadline has passed and late submissions are not accepted.")

        existing = AssignmentSubmission.objects.filter(assignment=assignment, student=user).first()
        if existing:
            if not assignment.allow_resubmission:
                raise ValidationError("You have already submitted and resubmission is disabled.")
            if existing.status == AssignmentSubmission.Status.GRADED:
                raise ValidationError("This submission has been graded and cannot be replaced.")
            for field, value in serializer.validated_data.items():
                if field != "assignment":
                    setattr(existing, field, value)
            existing.attempt += 1
            existing.submitted_at = now
            existing.status = (
                AssignmentSubmission.Status.LATE if late else AssignmentSubmission.Status.SUBMITTED
            )
            existing.updated_by = user
            existing.save()
            audit.record(AuditAction.UPDATE, obj=existing, description="Submission replaced")
            serializer.instance = existing
            return existing

        instance = serializer.save(
            student=user,
            created_by=user,
            updated_by=user,
            submitted_at=now,
            status=AssignmentSubmission.Status.LATE if late else AssignmentSubmission.Status.SUBMITTED,
        )
        audit.record(AuditAction.CREATE, obj=instance, description="Assignment submitted")
        return instance

    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        submission = self.get_object()
        if not request.user.has_perm_code(Perm.ASSIGNMENT_GRADE) or not teaches_section(
            request.user, submission.assignment.section
        ):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot grade this submission."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = GradeSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        marks = serializer.validated_data["marks_obtained"]
        if marks > submission.assignment.max_marks:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Marks cannot exceed the assignment maximum of %s."
                        % submission.assignment.max_marks,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission.marks_obtained = marks
        submission.feedback = serializer.validated_data.get("feedback", "")
        submission.status = serializer.validated_data["status"]
        submission.graded_at = timezone.now()
        submission.graded_by = request.user
        submission.save()

        # Feed the linked internal assessment component, if configured.
        component = submission.assignment.component
        if component is not None:
            from apps.assessments.models import ComponentScore
            from apps.assessments.services import recompute_result

            score, _ = ComponentScore.objects.get_or_create(
                component=component, student=submission.student
            )
            if not score.is_locked:
                scaled = (
                    float(marks) / float(submission.assignment.max_marks) * float(component.max_marks)
                    if submission.assignment.max_marks
                    else 0
                )
                score.marks_obtained = round(scaled, 2)
                score.updated_by = request.user
                score.save()
                recompute_result(submission.student, component.section)

        audit.record(
            AuditAction.MARKS_CHANGE,
            obj=submission,
            description="Assignment graded",
            metadata={"marks": str(marks)},
        )
        notify(
            [submission.student],
            event="ASSIGNMENT_GRADED",
            title="Your assignment has been graded",
            body="%s - %s/%s"
            % (submission.assignment.title, marks, submission.assignment.max_marks),
            link="/assignments/%s" % submission.assignment_id,
        )
        return Response(AssignmentSubmissionSerializer(submission).data)
