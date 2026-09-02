from rest_framework import serializers

from apps.settings_app.models import DashboardWidget, SystemSetting


class SystemSettingSerializer(serializers.ModelSerializer):
    typed_value = serializers.SerializerMethodField()

    class Meta:
        model = SystemSetting
        fields = [
            "id", "key", "label", "value", "typed_value", "value_type", "group",
            "description", "is_public", "is_editable", "display_order",
        ]
        read_only_fields = ["id", "typed_value"]

    def get_typed_value(self, obj):
        return obj.typed_value

    def validate(self, attrs):
        if self.instance and not self.instance.is_editable:
            raise serializers.ValidationError("This setting is locked and cannot be changed here.")
        value_type = attrs.get("value_type", getattr(self.instance, "value_type", None))
        value = attrs.get("value", getattr(self.instance, "value", ""))
        if value_type == SystemSetting.ValueType.NUMBER and value not in ("", None):
            try:
                float(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError({"value": "This setting must be a number."})
        if value_type == SystemSetting.ValueType.JSON and value:
            import json

            try:
                json.loads(value)
            except ValueError:
                raise serializers.ValidationError({"value": "This setting must be valid JSON."})
        if value_type == SystemSetting.ValueType.COLOR and value:
            if not (value.startswith("#") and len(value) in (4, 7)):
                raise serializers.ValidationError({"value": "Use a hex colour such as #0b4f6c."})
        return attrs


class DashboardWidgetSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = DashboardWidget
        fields = [
            "id", "widget_key", "label", "role", "role_display", "is_enabled",
            "display_order", "column_span", "config",
        ]
        read_only_fields = ["id"]
