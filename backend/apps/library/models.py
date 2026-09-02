"""Library / e-resource directory (brief section 38)."""
from django.db import models

from apps.core.models import BaseModel


class ResourceCategory(BaseModel):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=250, blank=True)
    icon = models.CharField(max_length=40, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "resource categories"

    def __str__(self):
        return self.name


class ResourceLink(BaseModel):
    class AccessType(models.TextChoices):
        OPEN = "OPEN", "Open access"
        INSTITUTIONAL = "INSTITUTIONAL", "Institutional login"
        SUBSCRIPTION = "SUBSCRIPTION", "Subscription"
        CAMPUS_ONLY = "CAMPUS_ONLY", "Campus network only"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ResourceCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="resources"
    )
    url = models.URLField()
    access_type = models.CharField(
        max_length=15, choices=AccessType.choices, default=AccessType.OPEN
    )
    access_instructions = models.TextField(blank=True)
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    tags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    click_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["title"]
        indexes = [models.Index(fields=["category", "is_active"])]

    def __str__(self):
        return self.title
