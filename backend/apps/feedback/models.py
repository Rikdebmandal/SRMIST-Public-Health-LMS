"""Configurable feedback forms (brief section 37).

Anonymous responses store no link back to the respondent; a separate
`FeedbackParticipation` row records *that* someone responded so the same person
cannot submit twice, without recording *what* they said.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class FeedbackForm(BaseModel):
    class FormType(models.TextChoices):
        COURSE = "COURSE", "Course feedback"
        FACULTY = "FACULTY", "Faculty feedback"
        EVENT = "EVENT", "Event feedback"
        WORKSHOP = "WORKSHOP", "Workshop feedback"
        PLATFORM = "PLATFORM", "LMS feedback"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    form_type = models.CharField(
        max_length=12, choices=FormType.choices, default=FormType.COURSE
    )
    is_anonymous = models.BooleanField(default=True)
    section = models.ForeignKey(
        "courses.CourseSection",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="feedback_forms",
    )
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="feedback_forms",
    )
    target_roles = models.JSONField(default=list, blank=True)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class FeedbackQuestion(BaseModel):
    class QuestionType(models.TextChoices):
        RATING = "RATING", "Rating scale"
        TEXT = "TEXT", "Free text"
        CHOICE = "CHOICE", "Single choice"
        MULTI_CHOICE = "MULTI_CHOICE", "Multiple choice"
        YES_NO = "YES_NO", "Yes / No"

    form = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE, related_name="questions")
    text = models.CharField(max_length=400)
    question_type = models.CharField(
        max_length=15, choices=QuestionType.choices, default=QuestionType.RATING
    )
    choices = models.JSONField(default=list, blank=True)
    scale_min = models.PositiveSmallIntegerField(default=1)
    scale_max = models.PositiveSmallIntegerField(default=5)
    is_required = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return self.text[:60]


class FeedbackResponse(BaseModel):
    """One submission. `respondent` stays NULL on anonymous forms, by design."""

    form = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE, related_name="responses")
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="feedback_responses",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]


class FeedbackAnswer(BaseModel):
    response = models.ForeignKey(
        FeedbackResponse, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        FeedbackQuestion, on_delete=models.CASCADE, related_name="answers"
    )
    rating_value = models.PositiveSmallIntegerField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    choice_value = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [("response", "question")]


class FeedbackParticipation(BaseModel):
    """Records that a user responded, without linking them to their answers."""

    form = models.ForeignKey(
        FeedbackForm, on_delete=models.CASCADE, related_name="participations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_participations"
    )

    class Meta:
        unique_together = [("form", "user")]
