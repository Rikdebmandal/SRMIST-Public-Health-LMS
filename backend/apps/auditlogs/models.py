"""Immutable audit trail (brief section 40).

Rows are append-only: `save()` refuses updates and `delete()` raises. Only a
database superuser can alter history, which is the point.
"""
import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    LOGIN = "LOGIN", "Login"
    LOGIN_FAILED = "LOGIN_FAILED", "Failed login"
    LOGOUT = "LOGOUT", "Logout"
    PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password change"
    PASSWORD_RESET = "PASSWORD_RESET", "Password reset"
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    ROLE_CHANGE = "ROLE_CHANGE", "Role change"
    MARKS_CHANGE = "MARKS_CHANGE", "Marks modification"
    MARKS_PUBLISH = "MARKS_PUBLISH", "Marks published"
    ATTENDANCE_CHANGE = "ATTENDANCE_CHANGE", "Attendance modification"
    FILE_UPLOAD = "FILE_UPLOAD", "File upload"
    FILE_DELETE = "FILE_DELETE", "File deletion"
    EXPORT = "EXPORT", "Data export"
    PERMISSION_DENIED = "PERMISSION_DENIED", "Permission denied"
    SETTINGS_CHANGE = "SETTINGS_CHANGE", "Settings change"


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    actor_email = models.EmailField(blank=True, help_text="Retained if the user is later removed.")
    actor_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=25, choices=AuditAction.choices, db_index=True)
    object_type = models.CharField(max_length=80, blank=True, db_index=True)
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    object_label = models.CharField(max_length=250, blank=True)
    description = models.CharField(max_length=400, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return "%s %s %s" % (self.actor_email or "system", self.action, self.object_label)

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("Audit log entries are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit log entries cannot be deleted.")
