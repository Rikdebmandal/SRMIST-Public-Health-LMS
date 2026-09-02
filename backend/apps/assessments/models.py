"""Configurable assessment components, marks workflow and grading.

Components (assignment / quiz / mid-term / seminar ...) are rows, not an enum,
so each course can define its own internal-mark structure (brief sections 19-21).
Published marks are locked and only re-openable through an audited workflow
(brief sections 80, 81).
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class GradeScale(BaseModel):
    """A named set of grade bands. Institutions may run several in parallel."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=250, blank=True)
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="grade_scales",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def resolve_for(cls, department=None):
        if department is not None:
            scale = cls.objects.filter(department=department, is_active=True).first()
            if scale:
                return scale
        return cls.objects.filter(is_default=True, is_active=True).first()


class GradeBand(BaseModel):
    scale = models.ForeignKey(GradeScale, on_delete=models.CASCADE, related_name="bands")
    letter = models.CharField(max_length=5)
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    description = models.CharField(max_length=100, blank=True)
    is_pass = models.BooleanField(default=True)

    class Meta:
        ordering = ["-min_percentage"]
        unique_together = [("scale", "letter")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_percentage__gte=models.F("min_percentage")),
                name="grade_band_range_valid",
            )
        ]

    def __str__(self):
        return "%s (%s%%+)" % (self.letter, self.min_percentage)


class AssessmentComponent(BaseModel):
    """One weighted piece of a course's internal assessment."""

    class Kind(models.TextChoices):
        ASSIGNMENT = "ASSIGNMENT", "Assignment"
        QUIZ = "QUIZ", "Quiz"
        ATTENDANCE = "ATTENDANCE", "Attendance"
        SEMINAR = "SEMINAR", "Seminar"
        PRESENTATION = "PRESENTATION", "Presentation"
        MIDTERM = "MIDTERM", "Mid-term"
        PROJECT = "PROJECT", "Project"
        PRACTICAL = "PRACTICAL", "Practical"
        VIVA = "VIVA", "Viva"
        OTHER = "OTHER", "Other"

    section = models.ForeignKey(
        "courses.CourseSection", on_delete=models.CASCADE, related_name="assessment_components"
    )
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ASSIGNMENT)
    max_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=100, validators=[MinValueValidator(0)]
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Contribution to the internal total, in marks.",
    )
    is_auto_calculated = models.BooleanField(
        default=False, help_text="Derived from attendance or assignment data instead of manual entry."
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = [("section", "name")]

    def __str__(self):
        return "%s (%s)" % (self.name, self.section.course.code)


class ComponentScore(BaseModel):
    """A single student's mark for one component, with a publication workflow."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted for review"
        REVIEWED = "REVIEWED", "Reviewed"
        PUBLISHED = "PUBLISHED", "Published"

    component = models.ForeignKey(
        AssessmentComponent, on_delete=models.CASCADE, related_name="scores"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="component_scores"
    )
    marks_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    is_absent = models.BooleanField(default=False)
    remarks = models.CharField(max_length=250, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="published_scores",
    )

    class Meta:
        ordering = ["student__full_name"]
        unique_together = [("component", "student")]
        indexes = [models.Index(fields=["student", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(marks_obtained__gte=0) | models.Q(marks_obtained__isnull=True),
                name="component_score_non_negative",
            )
        ]

    def __str__(self):
        return "%s - %s" % (self.student.full_name, self.component.name)

    @property
    def is_locked(self) -> bool:
        return self.status == self.Status.PUBLISHED


class ExternalMark(BaseModel):
    """University / external examination marks (brief section 20)."""

    class Kind(models.TextChoices):
        THEORY = "THEORY", "University theory"
        PRACTICAL = "PRACTICAL", "Practical"
        VIVA = "VIVA", "Viva"
        PROJECT = "PROJECT", "Project"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="external_marks"
    )
    section = models.ForeignKey(
        "courses.CourseSection", on_delete=models.CASCADE, related_name="external_marks"
    )
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.THEORY)
    marks_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0)]
    )
    max_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=100, validators=[MinValueValidator(1)]
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    exam_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["student__full_name"]
        unique_together = [("student", "section", "kind")]

    def __str__(self):
        return "%s - %s" % (self.student.full_name, self.kind)


class CourseResult(BaseModel):
    """Computed per-student result for a section. Recalculated, never hand-typed."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_results"
    )
    section = models.ForeignKey(
        "courses.CourseSection", on_delete=models.CASCADE, related_name="results"
    )
    internal_total = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    internal_max = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    external_total = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    external_max = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grade_letter = models.CharField(max_length=5, blank=True)
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    credits = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    is_pass = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name"]
        unique_together = [("student", "section")]
        indexes = [models.Index(fields=["section", "is_published"])]

    def __str__(self):
        return "%s - %s (%s)" % (self.student.full_name, self.section.course.code, self.grade_letter)
