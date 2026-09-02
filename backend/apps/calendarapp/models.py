"""Unified academic calendar (brief section 25).

Class meetings, exams, assignment deadlines, events and holidays are surfaced
through one endpoint; only `CalendarEvent` rows are stored here, the rest are
projected from their own tables at query time.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class EventCategory(models.TextChoices):
    ACADEMIC = "ACADEMIC", "Academic"
    EXAMINATION = "EXAMINATION", "Examination"
    ASSIGNMENT = "ASSIGNMENT", "Assignment"
    EVENT = "EVENT", "Event"
    SEMINAR = "SEMINAR", "Seminar"
    RESEARCH = "RESEARCH", "Research"
    HOLIDAY = "HOLIDAY", "Holiday"
    MEETING = "MEETING", "Meeting"
    PERSONAL = "PERSONAL", "Personal"


class CalendarEvent(BaseModel):
    class Audience(models.TextChoices):
        INSTITUTION = "INSTITUTION", "Institution-wide"
        DEPARTMENT = "DEPARTMENT", "Department"
        SECTION = "SECTION", "Course section"
        ROLE = "ROLE", "Role"
        PERSONAL = "PERSONAL", "Personal"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=15, choices=EventCategory.choices, default=EventCategory.EVENT
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=200, blank=True)
    online_url = models.URLField(blank=True)

    audience = models.CharField(
        max_length=15, choices=Audience.choices, default=Audience.DEPARTMENT
    )
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )
    section = models.ForeignKey(
        "courses.CourseSection",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )
    target_roles = models.JSONField(default=list, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="personal_events",
    )

    is_published = models.BooleanField(default=True)
    reminder_minutes = models.PositiveIntegerField(default=60)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["start_at", "category"]),
            models.Index(fields=["department", "start_at"]),
        ]

    def __str__(self):
        return "%s (%s)" % (self.title, self.start_at.date())


class EventRegistration(BaseModel):
    class Status(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        ATTENDED = "ATTENDED", "Attended"
        CANCELLED = "CANCELLED", "Cancelled"

    event = models.ForeignKey(
        CalendarEvent, on_delete=models.CASCADE, related_name="registrations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REGISTERED)

    class Meta:
        unique_together = [("event", "user")]
        ordering = ["-created_at"]
