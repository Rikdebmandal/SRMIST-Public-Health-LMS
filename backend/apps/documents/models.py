"""Notes and document repository with versioning (brief sections 14, 82)."""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class Note(BaseModel):
    """A teaching resource. The file itself lives on the active NoteVersion."""

    class Visibility(models.TextChoices):
        SECTION = "SECTION", "Enrolled students only"
        COURSE = "COURSE", "All students of the course"
        DEPARTMENT = "DEPARTMENT", "Whole department"
        INSTITUTION = "INSTITUTION", "Whole institution"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="notes"
    )
    section = models.ForeignKey(
        "courses.CourseSection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notes",
    )
    department = models.ForeignKey(
        "academics.Department", on_delete=models.CASCADE, related_name="notes"
    )
    semester_number = models.PositiveSmallIntegerField(default=1)
    topic = models.CharField(max_length=200, blank=True)
    tags = models.JSONField(default=list, blank=True)
    visibility = models.CharField(
        max_length=15, choices=Visibility.choices, default=Visibility.SECTION
    )
    allow_download = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)
    download_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course", "is_published"]),
            models.Index(fields=["department", "semester_number"]),
        ]

    def __str__(self):
        return self.title

    @property
    def active_version(self):
        return self.versions.filter(is_active=True).order_by("-version_number").first()


class NoteVersion(BaseModel):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveSmallIntegerField(default=1)
    file = models.FileField(upload_to="notes/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    changelog = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = [("note", "version_number")]

    def __str__(self):
        return "%s v%s" % (self.note.title, self.version_number)

    @property
    def extension(self) -> str:
        name = self.original_filename or (self.file.name if self.file else "")
        return name.rsplit(".", 1)[-1].lower() if "." in name else ""

    @property
    def size_display(self) -> str:
        size = float(self.file_size or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return "%.1f %s" % (size, unit)
            size /= 1024
        return "%.1f TB" % size


class NoteAccessLog(BaseModel):
    """Download/view telemetry, used by engagement analytics."""

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="access_logs")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="note_accesses"
    )
    action = models.CharField(
        max_length=10, choices=[("VIEW", "View"), ("DOWNLOAD", "Download")], default="VIEW"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]
