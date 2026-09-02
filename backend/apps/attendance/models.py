"""Attendance with a configurable policy and a draft/finalised/locked workflow.

Thresholds are never hard-coded - the 75% figure lives in an
:class:`AttendancePolicy` row an administrator can edit (brief sections 17, 18, 80).
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class AttendancePolicy(BaseModel):
    """Attendance rules, scoped institution-wide or per department."""

    name = models.CharField(max_length=100, default="Default attendance policy")
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendance_policies",
        help_text="Leave empty for the institution-wide default.",
    )
    warning_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    critical_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=65,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    consecutive_absence_alert = models.PositiveSmallIntegerField(
        default=3, help_text="Raise an alert after this many consecutive absences."
    )
    count_late_as_present = models.BooleanField(default=True)
    exclude_excused_from_total = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department__name", "name"]
        verbose_name_plural = "attendance policies"

    def __str__(self):
        scope = self.department.code if self.department else "Institution"
        return "%s (%s)" % (self.name, scope)

    @classmethod
    def resolve_for(cls, department=None):
        """Department policy when present, otherwise the institution default."""
        if department is not None:
            policy = cls.objects.filter(department=department, is_active=True).first()
            if policy:
                return policy
        policy = cls.objects.filter(department__isnull=True, is_active=True).first()
        if policy:
            return policy
        return cls(name="Fallback", warning_threshold=75, critical_threshold=65)


class AttendanceSession(BaseModel):
    """One class meeting for which attendance is taken."""

    class SessionType(models.TextChoices):
        LECTURE = "LECTURE", "Lecture"
        PRACTICAL = "PRACTICAL", "Practical"
        TUTORIAL = "TUTORIAL", "Tutorial"
        SEMINAR = "SEMINAR", "Seminar"
        FIELD_WORK = "FIELD_WORK", "Field work"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        FINALIZED = "FINALIZED", "Finalised"
        LOCKED = "LOCKED", "Locked"

    section = models.ForeignKey(
        "courses.CourseSection", on_delete=models.CASCADE, related_name="attendance_sessions"
    )
    date = models.DateField(db_index=True)
    period = models.PositiveSmallIntegerField(
        default=1, help_text="Period number within the day."
    )
    session_type = models.CharField(
        max_length=20, choices=SessionType.choices, default=SessionType.LECTURE
    )
    topic = models.CharField(max_length=250, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_sessions_marked",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "period"]
        unique_together = [("section", "date", "period")]
        indexes = [models.Index(fields=["section", "date"])]

    def __str__(self):
        return "%s - %s P%s" % (self.section, self.date, self.period)

    @property
    def is_editable(self) -> bool:
        return self.status != self.Status.LOCKED


class AttendanceRecord(BaseModel):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        EXCUSED = "EXCUSED", "Excused"

    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="records"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    remarks = models.CharField(max_length=250, blank=True)
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name"]
        unique_together = [("session", "student")]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["session", "status"]),
        ]

    def __str__(self):
        return "%s - %s" % (self.student.full_name, self.status)


class AttendanceAlert(BaseModel):
    """A generated warning, kept so it can be acknowledged and audited."""

    class Level(models.TextChoices):
        WARNING = "WARNING", "Warning"
        CRITICAL = "CRITICAL", "Critical"
        CONSECUTIVE = "CONSECUTIVE", "Consecutive absences"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_alerts"
    )
    section = models.ForeignKey(
        "courses.CourseSection",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attendance_alerts",
    )
    level = models.CharField(max_length=15, choices=Level.choices)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    message = models.CharField(max_length=300)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "level"])]

    def __str__(self):
        return "%s - %s" % (self.student.full_name, self.level)
