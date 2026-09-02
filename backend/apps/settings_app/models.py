"""Database-driven system settings, branding and dashboard widgets
(brief sections 41, 42, 62)."""
from django.core.cache import cache
from django.db import models

from apps.core.models import BaseModel
from apps.core.rbac import Roles

SETTINGS_CACHE_KEY = "system_settings_map"
SETTINGS_CACHE_TTL = 300


class SystemSetting(BaseModel):
    """A single typed, namespaced configuration value."""

    class ValueType(models.TextChoices):
        STRING = "STRING", "String"
        NUMBER = "NUMBER", "Number"
        BOOLEAN = "BOOLEAN", "Boolean"
        JSON = "JSON", "JSON"
        COLOR = "COLOR", "Colour"

    class Group(models.TextChoices):
        BRANDING = "BRANDING", "Branding"
        ACADEMIC = "ACADEMIC", "Academic"
        NOTIFICATION = "NOTIFICATION", "Notifications"
        SECURITY = "SECURITY", "Security"
        UPLOAD = "UPLOAD", "Uploads"
        GENERAL = "GENERAL", "General"

    key = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=150)
    value = models.TextField(blank=True)
    value_type = models.CharField(
        max_length=10, choices=ValueType.choices, default=ValueType.STRING
    )
    group = models.CharField(max_length=15, choices=Group.choices, default=Group.GENERAL)
    description = models.CharField(max_length=300, blank=True)
    is_public = models.BooleanField(
        default=False, help_text="Public settings are readable without authentication."
    )
    is_editable = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["group", "display_order", "key"]

    def __str__(self):
        return self.key

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(SETTINGS_CACHE_KEY)

    @property
    def typed_value(self):
        raw = self.value
        if self.value_type == self.ValueType.NUMBER:
            try:
                return float(raw) if "." in str(raw) else int(raw)
            except (TypeError, ValueError):
                return 0
        if self.value_type == self.ValueType.BOOLEAN:
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}
        if self.value_type == self.ValueType.JSON:
            import json

            try:
                return json.loads(raw or "null")
            except ValueError:
                return None
        return raw

    @classmethod
    def as_map(cls) -> dict:
        cached = cache.get(SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached
        data = {item.key: item.typed_value for item in cls.objects.all()}
        cache.set(SETTINGS_CACHE_KEY, data, SETTINGS_CACHE_TTL)
        return data

    @classmethod
    def get_value(cls, key, default=None):
        return cls.as_map().get(key, default)


class DashboardWidget(BaseModel):
    """Which widgets appear on which role's dashboard (brief section 62)."""

    widget_key = models.SlugField(max_length=60)
    label = models.CharField(max_length=120)
    role = models.CharField(max_length=20, choices=Roles.CHOICES)
    is_enabled = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    column_span = models.PositiveSmallIntegerField(default=1)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["role", "display_order"]
        unique_together = [("widget_key", "role")]

    def __str__(self):
        return "%s / %s" % (self.role, self.widget_key)
