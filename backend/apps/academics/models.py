"""Institutional structure: departments, programs, sessions, semesters, batches.

Nothing here hard-codes a single department or program (brief section 10) - the
School of Public Health is simply the first tenant of the structure.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class Department(BaseModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    hod = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="headed_departments",
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    established_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return "%s (%s)" % (self.name, self.code)


class Program(BaseModel):
    class Level(models.TextChoices):
        UG = "UG", "Undergraduate"
        PG = "PG", "Postgraduate"
        DIPLOMA = "DIPLOMA", "Diploma"
        CERTIFICATE = "CERTIFICATE", "Certificate"
        DOCTORAL = "DOCTORAL", "Doctoral"

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="programs")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.PG)
    duration_years = models.PositiveSmallIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    total_semesters = models.PositiveSmallIntegerField(
        default=4, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    total_credits = models.PositiveSmallIntegerField(default=80)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return "%s (%s)" % (self.name, self.code)


class AcademicSession(BaseModel):
    """An academic year, e.g. 2025-26."""

    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="session_end_after_start",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            AcademicSession.objects.exclude(pk=self.pk).filter(is_current=True).update(
                is_current=False
            )


class Semester(BaseModel):
    session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, related_name="semesters"
    )
    number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    name = models.CharField(max_length=60, help_text="e.g. 'Semester 1 (Odd)'")
    start_date = models.DateField()
    end_date = models.DateField()
    exam_start_date = models.DateField(null=True, blank=True)
    exam_end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False, db_index=True)
    result_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["session__start_date", "number"]
        unique_together = [("session", "number")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="semester_end_after_start",
            )
        ]

    def __str__(self):
        return "%s - %s" % (self.session.name, self.name)


class Batch(BaseModel):
    """A cohort admitted into a program in a given year."""

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="batches")
    name = models.CharField(max_length=100)
    start_year = models.PositiveSmallIntegerField()
    end_year = models.PositiveSmallIntegerField()
    current_semester = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_year", "name"]
        unique_together = [("program", "start_year", "name")]

    def __str__(self):
        return self.name


class CurriculumItem(BaseModel):
    """One course slot in a program's curriculum (brief section 13)."""

    class Category(models.TextChoices):
        CORE = "CORE", "Core"
        ELECTIVE = "ELECTIVE", "Elective"
        PRACTICAL = "PRACTICAL", "Practical"
        SEMINAR = "SEMINAR", "Seminar"
        PROJECT = "PROJECT", "Project"
        INTERNSHIP = "INTERNSHIP", "Internship"
        FOUNDATION = "FOUNDATION", "Foundation"

    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="curriculum_items")
    batch = models.ForeignKey(
        Batch, null=True, blank=True, on_delete=models.CASCADE, related_name="curriculum_items"
    )
    semester_number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="curriculum_items"
    )
    credits = models.DecimalField(max_digits=4, decimal_places=1, default=3)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.CORE)
    is_mandatory = models.BooleanField(default=True)
    prerequisites = models.ManyToManyField(
        "courses.Course", blank=True, related_name="required_for_curriculum_items"
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["program", "semester_number", "display_order"]
        unique_together = [("program", "batch", "semester_number", "course")]

    def __str__(self):
        return "%s / Sem %s / %s" % (self.program.code, self.semester_number, self.course.code)


class Holiday(BaseModel):
    session = models.ForeignKey(
        AcademicSession, on_delete=models.CASCADE, related_name="holidays"
    )
    name = models.CharField(max_length=150)
    date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True)
    is_working_day = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]
        unique_together = [("session", "name", "date")]

    def __str__(self):
        return "%s (%s)" % (self.name, self.date)
