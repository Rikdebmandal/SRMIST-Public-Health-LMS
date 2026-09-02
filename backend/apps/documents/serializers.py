from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.validators import validate_upload
from apps.documents.models import Note, NoteVersion


class NoteVersionSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    size_display = serializers.CharField(read_only=True)
    extension = serializers.CharField(read_only=True)

    class Meta:
        model = NoteVersion
        fields = [
            "id", "note", "version_number", "file", "original_filename", "file_size",
            "content_type", "changelog", "is_active", "uploaded_by", "size_display",
            "extension", "created_at",
        ]
        read_only_fields = [
            "id", "version_number", "file_size", "content_type", "original_filename", "created_at",
        ]

    def validate_file(self, value):
        try:
            validate_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value


class NoteSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    uploaded_by = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    active_version_detail = serializers.SerializerMethodField()
    version_count = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            "id", "title", "description", "course", "course_code", "course_name", "section",
            "department", "department_name", "semester_number", "topic", "tags", "visibility",
            "allow_download", "is_published", "download_count", "view_count", "uploaded_by",
            "active_version_detail", "version_count", "created_at",
        ]
        read_only_fields = ["id", "download_count", "view_count", "created_at"]

    def get_active_version_detail(self, obj):
        version = obj.active_version
        if version is None:
            return None
        return NoteVersionSerializer(version, context=self.context).data

    def get_version_count(self, obj):
        return obj.versions.count()


class NoteUploadSerializer(serializers.Serializer):
    """Create a note and its first version in one multipart request."""

    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    course = serializers.UUIDField()
    section = serializers.UUIDField(required=False, allow_null=True)
    semester_number = serializers.IntegerField(default=1, min_value=1)
    topic = serializers.CharField(required=False, allow_blank=True, max_length=200)
    tags = serializers.CharField(required=False, allow_blank=True)
    visibility = serializers.ChoiceField(
        choices=Note.Visibility.choices, default=Note.Visibility.SECTION
    )
    allow_download = serializers.BooleanField(default=True)
    file = serializers.FileField()
    changelog = serializers.CharField(required=False, allow_blank=True, max_length=300)

    def validate_file(self, value):
        try:
            validate_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value
