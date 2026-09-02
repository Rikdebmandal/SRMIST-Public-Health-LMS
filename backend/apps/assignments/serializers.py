from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.core.validators import validate_upload


class AssignmentSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="section.course.code", read_only=True)
    course_name = serializers.CharField(source="section.course.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    is_open = serializers.BooleanField(read_only=True)
    submission_stats = serializers.SerializerMethodField()
    my_submission = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id", "section", "course_code", "course_name", "section_name", "title",
            "description", "instructions", "attachment", "max_marks", "published_at",
            "due_date", "allow_late_submission", "late_penalty_percent", "allowed_extensions",
            "max_file_size_mb", "allow_resubmission", "component", "status", "is_open",
            "submission_stats", "my_submission", "created_at",
        ]
        read_only_fields = ["id", "created_at", "published_at"]

    def get_submission_stats(self, obj):
        request = self.context.get("request")
        if request and request.user.role == "STUDENT":
            return None
        from apps.courses.models import Enrollment

        total = obj.section.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
        submissions = obj.submissions.all()
        graded = sum(1 for s in submissions if s.status == AssignmentSubmission.Status.GRADED)
        late = sum(1 for s in submissions if s.status == AssignmentSubmission.Status.LATE)
        return {
            "enrolled": total,
            "submitted": len(submissions),
            "pending": max(total - len(submissions), 0),
            "graded": graded,
            "late": late,
        }

    def get_my_submission(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        submission = obj.submissions.filter(student=request.user).first()
        if submission is None:
            return None
        return {
            "id": str(submission.id),
            "status": submission.status,
            "submitted_at": submission.submitted_at,
            "marks_obtained": float(submission.marks_obtained)
            if submission.marks_obtained is not None
            else None,
            "feedback": submission.feedback,
            "file": submission.file.url if submission.file else None,
            "is_late": submission.is_late,
        }

    def validate_due_date(self, value):
        if not self.instance and value <= timezone.now():
            raise serializers.ValidationError("The due date must be in the future.")
        return value

    def validate_attachment(self, value):
        if value:
            try:
                validate_upload(value)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.messages)
        return value


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    assignment_title = serializers.CharField(source="assignment.title", read_only=True)
    max_marks = serializers.DecimalField(
        source="assignment.max_marks", max_digits=6, decimal_places=2, read_only=True
    )
    enrollment_number = serializers.CharField(
        source="student.student_profile.enrollment_number", read_only=True, default=""
    )
    is_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id", "assignment", "assignment_title", "max_marks", "student", "student_detail",
            "enrollment_number", "file", "text_response", "submitted_at", "status", "attempt",
            "marks_obtained", "feedback", "graded_at", "graded_by", "is_late",
        ]
        read_only_fields = [
            "id", "submitted_at", "status", "attempt", "graded_at", "graded_by", "student",
        ]

    def validate_file(self, value):
        if value:
            assignment = None
            if self.instance:
                assignment = self.instance.assignment
            else:
                assignment_id = self.initial_data.get("assignment")
                assignment = Assignment.objects.filter(pk=assignment_id).first()
            allowed = (assignment.allowed_extensions if assignment else None) or None
            max_mb = assignment.max_file_size_mb if assignment else settings.MAX_UPLOAD_SIZE_MB
            try:
                validate_upload(value, allowed_extensions=allowed, max_size_mb=max_mb)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.messages)
        return value

    def validate(self, attrs):
        if not attrs.get("file") and not attrs.get("text_response") and not self.instance:
            raise serializers.ValidationError(
                "Attach a file or write a response before submitting."
            )
        return attrs


class GradeSubmissionSerializer(serializers.Serializer):
    marks_obtained = serializers.DecimalField(
        max_digits=6, decimal_places=2, min_value=Decimal("0")
    )
    feedback = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=[AssignmentSubmission.Status.GRADED, AssignmentSubmission.Status.RETURNED],
        default=AssignmentSubmission.Status.GRADED,
    )
