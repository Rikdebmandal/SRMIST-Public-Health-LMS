from rest_framework import serializers

from apps.library.models import ResourceCategory, ResourceLink


class ResourceCategorySerializer(serializers.ModelSerializer):
    resource_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = ResourceCategory
        fields = ["id", "name", "description", "icon", "display_order", "is_active", "resource_count"]
        read_only_fields = ["id"]


class ResourceLinkSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    access_display = serializers.CharField(source="get_access_type_display", read_only=True)

    class Meta:
        model = ResourceLink
        fields = [
            "id", "title", "description", "category", "category_name", "url", "access_type",
            "access_display", "access_instructions", "department", "tags", "is_active",
            "click_count",
        ]
        read_only_fields = ["id", "click_count"]
