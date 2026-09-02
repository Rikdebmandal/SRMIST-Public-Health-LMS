"""Configurable risk rules and stored risk snapshots (brief sections 30, 31, 89)."""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class RiskRule(BaseModel):
    """An administrator-editable rule in the Academic Support Risk Indicator."""

    class Operator(models.TextChoices):
        LT = "lt", "is less than"
        LTE = "lte", "is at most"
        GT = "gt", "is greater than"
        GTE = "gte", "is at least"
        EQ = "eq", "equals"

    class Metric(models.TextChoices):
        ATTENDANCE = "attendance_percentage", "Attendance percentage"
        AVERAGE = "average_percentage", "Average assessment percentage"
        MISSED_ASSIGNMENTS = "missed_assignments", "Missed assignments"
        SCORE_TREND = "score_trend", "Recent score trend"
        DAYS_INACTIVE = "days_inactive", "Days inactive"
        FAILED_ASSESSMENTS = "failed_assessments", "Failed assessments"

    code = models.SlugField(max_length=50, unique=True)
    label = models.CharField(max_length=150)
    metric = models.CharField(max_length=40, choices=Metric.choices)
    operator = models.CharField(max_length=5, choices=Operator.choices, default=Operator.LT)
    threshold = models.DecimalField(max_digits=8, decimal_places=2)
    weight = models.PositiveSmallIntegerField(default=10)
    guidance = models.CharField(max_length=300, blank=True)
    department = models.ForeignKey(
        "academics.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="risk_rules",
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-weight"]

    def __str__(self):
        return "%s (%s)" % (self.label, self.weight)

    def as_dict(self):
        return {
            "code": self.code,
            "label": self.label,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": float(self.threshold),
            "weight": int(self.weight),
            "guidance": self.guidance,
        }


class RiskSnapshot(BaseModel):
    """A point-in-time risk evaluation, retained so trends stay explainable."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="risk_snapshots"
    )
    score = models.PositiveSmallIntegerField(default=0)
    level = models.CharField(max_length=12, default="low")
    factors = models.JSONField(default=list, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_risk_snapshots",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "created_at"]), models.Index(fields=["level"])]

    def __str__(self):
        return "%s - %s (%s)" % (self.student.full_name, self.level, self.score)


class ActivityLog(BaseModel):
    """Lightweight engagement telemetry feeding the inactivity metric."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_logs"
    )
    action = models.CharField(max_length=60)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]
