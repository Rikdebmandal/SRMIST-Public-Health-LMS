"""Assignments and submissions (brief section 16)."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class Assignment(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        CLOSED = "CLOSED", "Closed"

    section = models.ForeignKey(
        "courses.CourseSection", on_delete=models.CASCADE, related_name="assignments"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    attachment = models.FileField(upload_to="assignments/%Y/%m/", null=True, blank=True)
    max_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=10, validators=[MinValueValidator(0)]
    )
    published_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(db_index=True)
    allow_late_submission = models.BooleanField(default=True)
    late_penalty_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    allowed_extensions = models.JSONField(default=list, blank=True)
    max_file_size_mb = models.PositiveSmallIntegerField(default=10)
    allow_resubmission = models.BooleanField(default=True)
    component = models.ForeignKey(
        "assessments.AssessmentComponent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assignments",
        help_text="Link grades straight into an internal assessment component.",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["-due_date"]
        indexes = [models.Index(fields=["section", "status"])]

    def __str__(self):
        return "%s (%s)" % (self.title, self.section.course.code)

    @property
    def is_open(self) -> bool:
        if self.status != self.Status.PUBLISHED:
            return False
        if timezone.now() <= self.due_date:
            return True
        return self.allow_late_submission


class AssignmentSubmission(BaseModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        LATE = "LATE", "Late"
        GRADED = "GRADED", "Graded"
        RETURNED = "RETURNED", "Returned for revision"

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignment_submissions"
    )
    file = models.FileField(upload_to="submissions/%Y/%m/", null=True, blank=True)
    text_response = models.TextField(blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    attempt = models.PositiveSmallIntegerField(default=1)

    marks_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="graded_submissions",
    )

    class Meta:
        ordering = ["-submitted_at"]
        unique_together = [("assignment", "student")]
        indexes = [models.Index(fields=["assignment", "status"])]

    def __str__(self):
        return "%s - %s" % (self.student.full_name, self.assignment.title)

    @property
    def is_late(self) -> bool:
        return self.submitted_at > self.assignment.due_date
