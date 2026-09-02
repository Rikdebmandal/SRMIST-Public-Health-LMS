from rest_framework import serializers

from apps.announcements.models import Announcement, AnnouncementCategory
from apps.core.rbac import Roles


class AnnouncementCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementCategory
        fields = ["id", "name", "color", "display_order", "is_active"]
        read_only_fields = ["id"]


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    course_code = serializers.CharField(source="course.code", read_only=True, default="")
    is_live = serializers.BooleanField(read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id", "title", "body", "category", "category_name", "priority", "audience",
            "department", "department_name", "course", "course_code", "section",
            "target_roles", "target_users", "attachment", "publish_at", "expires_at",
            "status", "is_pinned", "author_name", "is_live", "is_read", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_is_read(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.reads.filter(user=request.user).exists()

    def validate_target_roles(self, value):
        unknown = [role for role in value if role not in Roles.ALL]
        if unknown:
            raise serializers.ValidationError("Unknown roles: %s" % ", ".join(unknown))
        return value

    def validate(self, attrs):
        audience = attrs.get("audience", getattr(self.instance, "audience", None))
        required = {
            Announcement.Audience.DEPARTMENT: "department",
            Announcement.Audience.COURSE: "course",
            Announcement.Audience.SECTION: "section",
        }
        field = required.get(audience)
        if field and not attrs.get(field, getattr(self.instance, field, None)):
            raise serializers.ValidationError(
                {field: "This field is required for a %s announcement." % audience.lower()}
            )
        if audience == Announcement.Audience.ROLE and not attrs.get(
            "target_roles", getattr(self.instance, "target_roles", None)
        ):
            raise serializers.ValidationError(
                {"target_roles": "Select at least one role."}
            )
        publish_at = attrs.get("publish_at", getattr(self.instance, "publish_at", None))
        expires_at = attrs.get("expires_at", getattr(self.instance, "expires_at", None))
        if publish_at and expires_at and expires_at <= publish_at:
            raise serializers.ValidationError(
                {"expires_at": "The expiry must be after the publication time."}
            )
        return attrs
