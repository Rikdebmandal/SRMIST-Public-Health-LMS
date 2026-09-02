"""In-app / email notifications, per-user preferences and editable templates
(brief sections 23, 63, 86)."""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class NotificationEvent(models.TextChoices):
    NEW_ASSIGNMENT = "NEW_ASSIGNMENT", "New assignment"
    ASSIGNMENT_DEADLINE = "ASSIGNMENT_DEADLINE", "Assignment deadline reminder"
    ASSIGNMENT_GRADED = "ASSIGNMENT_GRADED", "Assignment graded"
    NEW_NOTE = "NEW_NOTE", "New notes uploaded"
    MARKS_PUBLISHED = "MARKS_PUBLISHED", "Marks published"
    ATTENDANCE_WARNING = "ATTENDANCE_WARNING", "Attendance warning"
    ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
    EVENT_REMINDER = "EVENT_REMINDER", "Event reminder"
    MENTORSHIP_REQUEST = "MENTORSHIP_REQUEST", "Mentorship request"
    JOB_OPPORTUNITY = "JOB_OPPORTUNITY", "Job opportunity"
    WEEKLY_DIGEST = "WEEKLY_DIGEST", "Weekly digest"
    FORUM_REPLY = "FORUM_REPLY", "Discussion reply"
    ACCOUNT = "ACCOUNT", "Account and security"


class NotificationTemplate(BaseModel):
    """Editable message template with {{placeholder}} support."""

    event = models.CharField(max_length=30, choices=NotificationEvent.choices, unique=True)
    subject = models.CharField(max_length=200)
    body = models.TextField(help_text="Supports {{placeholders}} such as {{student_name}}.")
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["event"]

    def __str__(self):
        return self.get_event_display()

    def render(self, context: dict):
        subject, body = self.subject, self.body
        for key, value in (context or {}).items():
            token = "{{%s}}" % key
            subject = subject.replace(token, str(value))
            body = body.replace(token, str(value))
        return subject, body


class Notification(BaseModel):
    class Level(models.TextChoices):
        INFO = "INFO", "Info"
        SUCCESS = "SUCCESS", "Success"
        WARNING = "WARNING", "Warning"
        CRITICAL = "CRITICAL", "Critical"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    event = models.CharField(max_length=30, choices=NotificationEvent.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    link = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self):
        return "%s -> %s" % (self.title, self.recipient.email)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationPreference(BaseModel):
    """One row per user per event - absent rows fall back to the template defaults."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    event = models.CharField(max_length=30, choices=NotificationEvent.choices)
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=True)
    push = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "event")]
        ordering = ["event"]

    def __str__(self):
        return "%s / %s" % (self.user.email, self.event)


class DigestSubscription(BaseModel):
    """Weekly academic digest delivery settings (brief section 24)."""

    class Frequency(models.TextChoices):
        WEEKLY = "WEEKLY", "Weekly"
        FORTNIGHTLY = "FORTNIGHTLY", "Fortnightly"
        OFF = "OFF", "Off"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="digest_subscription"
    )
    frequency = models.CharField(
        max_length=12, choices=Frequency.choices, default=Frequency.WEEKLY
    )
    day_of_week = models.PositiveSmallIntegerField(default=0, help_text="0 = Monday")
    send_email = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return "%s (%s)" % (self.user.email, self.frequency)
