from rest_framework import serializers

from apps.notifications.models import (
    DigestSubscription,
    Notification,
    NotificationEvent,
    NotificationPreference,
    NotificationTemplate,
)


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)
    event_display = serializers.CharField(source="get_event_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "event", "event_display", "title", "body", "level", "link", "metadata",
            "read_at", "is_read", "created_at",
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    event_display = serializers.CharField(source="get_event_display", read_only=True)

    class Meta:
        model = NotificationPreference
        fields = ["id", "event", "event_display", "in_app", "email", "push"]
        read_only_fields = ["id"]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    event_display = serializers.CharField(source="get_event_display", read_only=True)
    placeholders = serializers.SerializerMethodField()

    class Meta:
        model = NotificationTemplate
        fields = [
            "id", "event", "event_display", "subject", "body", "email_enabled",
            "in_app_enabled", "is_active", "placeholders",
        ]
        read_only_fields = ["id"]

    def get_placeholders(self, obj):
        return ["student_name", "user_name", "course_name", "deadline", "title", "body"]


class DigestSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DigestSubscription
        fields = ["id", "frequency", "day_of_week", "send_email", "last_sent_at"]
        read_only_fields = ["id", "last_sent_at"]


class EventCatalogueSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def catalogue():
        return [{"code": code, "label": label} for code, label in NotificationEvent.choices]
