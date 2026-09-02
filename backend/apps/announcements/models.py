"""Targeted announcements with a draft/published/expired lifecycle (brief section 22)."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.core.rbac import Roles


class AnnouncementCategory(BaseModel):
    name = models.CharField(max_length=60, unique=True)
    color = models.CharField(max_length=20, default="slate")
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "announcement categories"

    def __str__(self):
        return self.name


class Announcement(BaseModel):
    class Priority(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        IMPORTANT = "IMPORTANT", "Important"
        URGENT = "URGENT", "Urgent"

    class Audience(models.TextChoices):
        INSTITUTION = "INSTITUTION", "Institution-wide"
        SCHOOL = "SCHOOL", "School-wide"
        DEPARTMENT = "DEPARTMENT", "Department"
        COURSE = "COURSE", "Course"
        SECTION = "SECTION", "Section"
        ROLE = "ROLE", "Specific role"
        INDIVIDUAL = "INDIVIDUAL", "Specific people"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        EXPIRED = "EXPIRED", "Expired"
        ARCHIVED = "ARCHIVED", "Archived"

    title = models.CharField(max_length=200)
    body = models.TextField()
    category = models.ForeignKey(
        AnnouncementCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="announcements",
    )
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.NORMAL)
    audience = models.CharField(
        max_length=15, choices=Audience.choices, default=Audience.DEPARTMENT
    )

    # Targeting - only the field matching `audience` is used.
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    course = models.ForeignKey(
        "courses.Course", null=True, blank=True, on_delete=models.CASCADE, related_name="announcements"
    )
    section = models.ForeignKey(
        "courses.CourseSection",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    target_roles = models.JSONField(default=list, blank=True)
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="targeted_announcements"
    )

    attachment = models.FileField(upload_to="announcements/%Y/%m/", null=True, blank=True)
    publish_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_pinned", "-publish_at"]
        indexes = [
            models.Index(fields=["status", "publish_at"]),
            models.Index(fields=["audience", "department"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        if self.status != self.Status.PUBLISHED or self.publish_at > now:
            return False
        return self.expires_at is None or self.expires_at > now

    def visible_to(self, user) -> bool:
        """Server-side audience check - mirrored by the queryset filter in views."""
        if not self.is_live:
            return False
        if self.audience in (self.Audience.INSTITUTION, self.Audience.SCHOOL):
            return True
        if self.audience == self.Audience.DEPARTMENT:
            return user.department_id == self.department_id
        if self.audience == self.Audience.ROLE:
            return user.role in (self.target_roles or Roles.ALL)
        if self.audience == self.Audience.INDIVIDUAL:
            return self.target_users.filter(pk=user.pk).exists()
        if self.audience == self.Audience.COURSE:
            return user.enrollments.filter(
                section__course_id=self.course_id, status="ACTIVE"
            ).exists()
        if self.audience == self.Audience.SECTION:
            return user.enrollments.filter(section_id=self.section_id, status="ACTIVE").exists()
        return False


class AnnouncementRead(BaseModel):
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="reads"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcement_reads"
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("announcement", "user")]
