from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasPerm, Perm
from apps.core.viewsets import AuditedModelViewSet
from apps.notifications.models import (
    DigestSubscription,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)
from apps.notifications.serializers import (
    DigestSubscriptionSerializer,
    EventCatalogueSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
    NotificationTemplateSerializer,
)
from apps.notifications.services import build_weekly_digest


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """A user only ever sees their own notifications."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["event", "level"]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response(
            {"count": self.get_queryset().filter(read_at__isnull=True).count()}
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated})


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"])
    def catalogue(self, request):
        return Response(EventCatalogueSerializer.catalogue())

    @action(detail=False, methods=["put"], url_path="bulk")
    def bulk_update(self, request):
        """Replace the caller's whole preference set in one call."""
        rows = request.data.get("preferences", [])
        for row in rows:
            event = row.get("event")
            if not event:
                continue
            NotificationPreference.objects.update_or_create(
                user=request.user,
                event=event,
                defaults={
                    "in_app": bool(row.get("in_app", True)),
                    "email": bool(row.get("email", False)),
                    "push": bool(row.get("push", False)),
                },
            )
        return Response(
            NotificationPreferenceSerializer(self.get_queryset(), many=True).data
        )


class NotificationTemplateViewSet(AuditedModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = Perm.SETTINGS_MANAGE
    required_write_permission = Perm.SETTINGS_MANAGE
    pagination_class = None
    audit_object_type = "notification template"


class DigestViewSet(viewsets.GenericViewSet):
    serializer_class = DigestSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DigestSubscription.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get", "put"], url_path="subscription")
    def subscription(self, request):
        subscription, _ = DigestSubscription.objects.get_or_create(user=request.user)
        if request.method == "PUT":
            serializer = DigestSubscriptionSerializer(
                subscription, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(DigestSubscriptionSerializer(subscription).data)

    @action(detail=False, methods=["get"], url_path="preview")
    def preview(self, request):
        """Render this week's digest for the caller without sending anything."""
        return Response(build_weekly_digest(request.user))
