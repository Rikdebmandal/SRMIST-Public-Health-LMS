from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers

from apps.auditlogs.models import AuditAction, AuditLog
from apps.core.permissions import HasPerm, Perm, Roles


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default="System")

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_name", "actor_email", "actor_role", "action",
            "action_display", "object_type", "object_id", "object_label", "description",
            "metadata", "ip_address", "created_at",
        ]
        read_only_fields = fields


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only by design - the model itself refuses updates and deletes."""

    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = Perm.AUDIT_VIEW
    filterset_fields = ["action", "actor", "object_type"]
    search_fields = ["actor_email", "object_label", "description"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # A department admin sees only their own department's actors.
        if user.role == Roles.ADMIN and user.department_id and not user.is_superuser:
            qs = qs.filter(actor__department=user.department)
        return qs

    @action(detail=False, methods=["get"])
    def actions(self, request):
        return Response([{"code": code, "label": label} for code, label in AuditAction.choices])

    @action(detail=False, methods=["get"])
    def summary(self, request):
        from django.db.models import Count
        from django.db.models.functions import TruncDate

        qs = self.get_queryset()
        return Response(
            {
                "total": qs.count(),
                "by_action": list(
                    qs.values("action").annotate(count=Count("id")).order_by("-count")[:15]
                ),
                "daily": [
                    {"day": row["day"].isoformat() if row["day"] else None, "count": row["count"]}
                    for row in qs.annotate(day=TruncDate("created_at"))
                    .values("day")
                    .annotate(count=Count("id"))
                    .order_by("-day")[:30]
                ],
            }
        )
