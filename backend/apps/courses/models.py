"""Courses, sections, faculty assignment and enrolment (brief section 12)."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class CourseType(BaseModel):
    """Course categories are data, not an enum, so institutions can extend them."""

    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Course(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"

    code = models.CharField(max_length=20, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credits = models.DecimalField(max_digits=4, decimal_places=1, default=3)
    department = models.ForeignKey(
        "academics.Department", on_delete=models.PROTECT, related_name="courses"
    )
    program = models.ForeignKey(
        "academics.Program",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="courses",
    )
    semester_number = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    course_type = models.ForeignKey(
        CourseType, null=True, blank=True, on_delete=models.SET_NULL, related_name="courses"
    )
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coordinated_courses",
    )
    syllabus = models.TextField(blank=True)
    learning_outcomes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["semester_number", "code"]
        unique_together = [("code", "department")]
        indexes = [
            models.Index(fields=["department", "status"]),
            models.Index(fields=["semester_number"]),
        ]

    def __str__(self):
        return "%s - %s" % (self.code, self.name)


class CourseSection(BaseModel):
    """A deliverable instance of a course in one semester."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sections")
    semester = models.ForeignKey(
        "academics.Semester", on_delete=models.CASCADE, related_name="sections"
    )
    batch = models.ForeignKey(
        "academics.Batch", null=True, blank=True, on_delete=models.SET_NULL, related_name="sections"
    )
    name = models.CharField(max_length=30, default="A")
    capacity = models.PositiveSmallIntegerField(default=60)
    room = models.CharField(max_length=60, blank=True)
    schedule = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {day, start_time, end_time, room} slots.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["course__code", "name"]
        unique_together = [("course", "semester", "name")]

    def __str__(self):
        return "%s / %s (%s)" % (self.course.code, self.name, self.semester.name)

    @property
    def enrolled_count(self) -> int:
        return self.enrollments.filter(status=Enrollment.Status.ACTIVE).count()

    @property
    def primary_faculty(self):
        assignment = self.faculty_assignments.filter(is_active=True, is_primary=True).first()
        return assignment.faculty if assignment else None


class FacultyCourseAssignment(BaseModel):
    """Binds a faculty member (or TA scholar) to a section - the basis of RBAC scoping."""

    class AssignmentRole(models.TextChoices):
        INSTRUCTOR = "INSTRUCTOR", "Instructor"
        CO_INSTRUCTOR = "CO_INSTRUCTOR", "Co-instructor"
        TEACHING_ASSISTANT = "TEACHING_ASSISTANT", "Teaching assistant"
        GUEST = "GUEST", "Guest faculty"

    section = models.ForeignKey(
        CourseSection, on_delete=models.CASCADE, related_name="faculty_assignments"
    )
    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_assignments"
    )
    assignment_role = models.CharField(
        max_length=25, choices=AssignmentRole.choices, default=AssignmentRole.INSTRUCTOR
    )
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    assigned_on = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "faculty__full_name"]
        unique_together = [("section", "faculty")]
        indexes = [models.Index(fields=["faculty", "is_active"])]

    def __str__(self):
        return "%s -> %s" % (self.faculty.full_name, self.section)


class Enrollment(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        DROPPED = "DROPPED", "Dropped"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    section = models.ForeignKey(
        CourseSection, on_delete=models.CASCADE, related_name="enrollments"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    enrolled_on = models.DateField(auto_now_add=True)
    completed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["student__full_name"]
        unique_together = [("student", "section")]
        indexes = [
            models.Index(fields=["section", "status"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self):
        return "%s in %s" % (self.student.full_name, self.section)
