from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.analytics.models import ActivityLog, RiskRule, RiskSnapshot


class RiskRuleSerializer(serializers.ModelSerializer):
    metric_display = serializers.CharField(source="get_metric_display", read_only=True)
    operator_display = serializers.CharField(source="get_operator_display", read_only=True)

    class Meta:
        model = RiskRule
        fields = [
            "id", "code", "label", "metric", "metric_display", "operator", "operator_display",
            "threshold", "weight", "guidance", "department", "is_active", "display_order",
        ]
        read_only_fields = ["id"]

    def validate_weight(self, value):
        if value > 100:
            raise serializers.ValidationError("A single rule cannot contribute more than 100 points.")
        return value


class RiskSnapshotSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.full_name", read_only=True, default="")

    class Meta:
        model = RiskSnapshot
        fields = [
            "id", "student", "student_detail", "score", "level", "factors", "metrics",
            "reviewed_by", "reviewed_by_name", "reviewed_at", "review_note", "created_at",
        ]
        read_only_fields = ["id", "created_at", "score", "level", "factors", "metrics"]


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = ActivityLog
        fields = ["id", "user", "user_name", "action", "context", "created_at"]
        read_only_fields = fields
