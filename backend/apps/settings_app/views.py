from django.core.cache import cache
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm
from apps.core.viewsets import AuditedModelViewSet
from apps.settings_app.models import SETTINGS_CACHE_KEY, DashboardWidget, SystemSetting
from apps.settings_app.serializers import DashboardWidgetSerializer, SystemSettingSerializer


class SystemSettingViewSet(AuditedModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    required_permission = Perm.SETTINGS_MANAGE
    required_write_permission = Perm.SETTINGS_MANAGE
    filterset_fields = ["group", "is_public"]
    search_fields = ["key", "label"]
    pagination_class = None
    audit_object_type = "system setting"

    def get_permissions(self):
        if self.action == "public":
            return [AllowAny()]
        return super().get_permissions()

    def get_authenticators(self):
        return super().get_authenticators()

    @action(detail=False, methods=["get"], permission_classes=[AllowAny], authentication_classes=[])
    def public(self, request):
        """Branding and theme values needed before a user signs in."""
        settings_qs = SystemSetting.objects.filter(is_public=True)
        return Response({item.key: item.typed_value for item in settings_qs})

    @action(detail=False, methods=["put"], url_path="bulk")
    def bulk_update(self, request):
        updated = []
        for row in request.data.get("settings", []):
            key, value = row.get("key"), row.get("value")
            setting = SystemSetting.objects.filter(key=key, is_editable=True).first()
            if setting is None:
                continue
            setting.value = "" if value is None else str(value)
            setting.updated_by = request.user
            setting.save()
            updated.append(key)
        cache.delete(SETTINGS_CACHE_KEY)
        audit.record(
            AuditAction.SETTINGS_CHANGE,
            description="Updated %s settings" % len(updated),
            metadata={"keys": updated},
        )
        return Response({"updated": updated})


class DashboardWidgetViewSet(AuditedModelViewSet):
    queryset = DashboardWidget.objects.all()
    serializer_class = DashboardWidgetSerializer
    required_permission = Perm.SETTINGS_MANAGE
    required_write_permission = Perm.SETTINGS_MANAGE
    filterset_fields = ["role", "is_enabled"]
    pagination_class = None
    audit_object_type = "dashboard widget"

    @action(detail=False, methods=["get"], url_path="for-me")
    def for_me(self, request):
        """The widget layout configured for the caller's role."""
        widgets = DashboardWidget.objects.filter(role=request.user.role, is_enabled=True)
        return Response(DashboardWidgetSerializer(widgets, many=True).data)
