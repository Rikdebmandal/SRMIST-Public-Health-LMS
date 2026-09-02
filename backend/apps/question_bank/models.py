"""Reusable question bank (brief section 15)."""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class QuestionTopic(BaseModel):
    """Hierarchical topic tree - a topic may have a parent subtopic chain."""

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="question_topics"
    )
    name = models.CharField(max_length=150)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    description = models.CharField(max_length=300, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = [("course", "parent", "name")]

    def __str__(self):
        return "%s / %s" % (self.course.code, self.name)

    @property
    def full_path(self) -> str:
        parts, node, guard = [], self, 0
        while node is not None and guard < 10:
            parts.append(node.name)
            node = node.parent
            guard += 1
        return " > ".join(reversed(parts))


class Question(BaseModel):
    class QuestionType(models.TextChoices):
        MCQ = "MCQ", "Multiple choice (single answer)"
        MULTI = "MULTI", "Multiple answer"
        TRUE_FALSE = "TRUE_FALSE", "True / False"
        SHORT = "SHORT", "Short answer"
        LONG = "LONG", "Long answer"
        CASE_STUDY = "CASE_STUDY", "Case study"
        NUMERICAL = "NUMERICAL", "Numerical"
        ANALYTICAL = "ANALYTICAL", "Analytical"

    class Difficulty(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REVIEW = "REVIEW", "Under review"
        APPROVED = "APPROVED", "Approved"
        RETIRED = "RETIRED", "Retired"

    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="questions"
    )
    topic = models.ForeignKey(
        QuestionTopic, null=True, blank=True, on_delete=models.SET_NULL, related_name="questions"
    )
    text = models.TextField()
    question_type = models.CharField(
        max_length=15, choices=QuestionType.choices, default=QuestionType.MCQ
    )
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM
    )
    marks = models.DecimalField(
        max_digits=5, decimal_places=2, default=1, validators=[MinValueValidator(0)]
    )
    correct_answer = models.TextField(
        blank=True, help_text="Free-text answer key for non-objective question types."
    )
    explanation = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course", "status"]),
            models.Index(fields=["question_type", "difficulty"]),
        ]

    def __str__(self):
        return self.text[:70]

    @property
    def is_objective(self) -> bool:
        return self.question_type in (
            self.QuestionType.MCQ,
            self.QuestionType.MULTI,
            self.QuestionType.TRUE_FALSE,
        )


class QuestionOption(BaseModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return self.text[:50]
