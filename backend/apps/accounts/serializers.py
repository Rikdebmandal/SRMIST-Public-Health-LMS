"""Authentication, profile and user-management serializers."""
from django.contrib.auth import password_validation
from django.db import transaction
from django.utils.crypto import get_random_string
from rest_framework import serializers

from apps.accounts.models import (
    AlumniProfile,
    FacultyProfile,
    RolePermission,
    ScholarProfile,
    StudentProfile,
    User,
)
from apps.core.rbac import ALL_PERMISSIONS, PERMISSION_LABELS, Roles


class DepartmentBriefSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    code = serializers.CharField(read_only=True)


class StudentProfileSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True, default="")
    batch_name = serializers.CharField(source="batch.name", read_only=True, default="")

    class Meta:
        model = StudentProfile
        fields = [
            "id", "enrollment_number", "program", "program_name", "batch", "batch_name",
            "current_semester", "admission_date", "guardian_name", "guardian_phone", "address",
        ]
        read_only_fields = ["id"]


class FacultyProfileSerializer(serializers.ModelSerializer):
    designation_display = serializers.CharField(source="get_designation_display", read_only=True)

    class Meta:
        model = FacultyProfile
        fields = [
            "id", "employee_id", "designation", "designation_display", "specialization",
            "qualification", "date_of_joining", "office_location",
        ]
        read_only_fields = ["id"]


class ScholarProfileSerializer(serializers.ModelSerializer):
    supervisor_name = serializers.CharField(source="supervisor.full_name", read_only=True, default="")

    class Meta:
        model = ScholarProfile
        fields = [
            "id", "registration_number", "research_area", "supervisor", "supervisor_name",
            "scholar_type", "enrolment_year", "is_teaching_assistant", "thesis_title",
        ]
        read_only_fields = ["id"]


class AlumniProfileSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True, default="")

    class Meta:
        model = AlumniProfile
        fields = [
            "id", "graduation_year", "program", "program_name", "current_organization",
            "job_title", "location", "skills", "linkedin_url", "website_url",
            "is_available_for_mentorship", "mentorship_areas", "show_email", "show_phone",
            "show_in_directory",
        ]
        read_only_fields = ["id"]


class UserSerializer(serializers.ModelSerializer):
    """The canonical user payload returned to the frontend."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    department_code = serializers.CharField(source="department.code", read_only=True, default="")
    initials = serializers.CharField(read_only=True)
    permissions = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "avatar", "role", "role_display",
            "department", "department_name", "department_code", "bio", "is_active",
            "email_verified", "must_change_password", "theme_preference", "locale",
            "timezone_name", "date_joined", "last_active_at", "initials", "permissions",
            "profile",
        ]
        read_only_fields = ["id", "date_joined", "last_active_at", "email_verified"]

    def get_permissions(self, obj):
        return sorted(obj.permission_codes)

    def get_profile(self, obj):
        if obj.role == Roles.STUDENT and hasattr(obj, "student_profile"):
            return StudentProfileSerializer(obj.student_profile).data
        if obj.role in (Roles.FACULTY, Roles.DEAN, Roles.ADMIN) and hasattr(obj, "faculty_profile"):
            return FacultyProfileSerializer(obj.faculty_profile).data
        if obj.role == Roles.SCHOLAR and hasattr(obj, "scholar_profile"):
            return ScholarProfileSerializer(obj.scholar_profile).data
        if obj.role == Roles.ALUMNI and hasattr(obj, "alumni_profile"):
            return AlumniProfileSerializer(obj.alumni_profile).data
        return None


class UserBriefSerializer(serializers.ModelSerializer):
    """Minimal user shape for embedding in other payloads - no contact details."""

    initials = serializers.CharField(read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "role", "role_display", "avatar", "initials"]


class UserWriteSerializer(serializers.ModelSerializer):
    """Admin user creation / editing, including the nested role profile."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    student_profile = StudentProfileSerializer(required=False)
    faculty_profile = FacultyProfileSerializer(required=False)
    scholar_profile = ScholarProfileSerializer(required=False)
    alumni_profile = AlumniProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "role", "department", "bio", "is_active",
            "password", "must_change_password", "student_profile", "faculty_profile",
            "scholar_profile", "alumni_profile",
        ]

    def validate_password(self, value):
        if value:
            password_validation.validate_password(value)
        return value

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", None))
        if role == Roles.STUDENT:
            profile = attrs.get("student_profile") or {}
            if not self.instance and not profile.get("enrollment_number"):
                raise serializers.ValidationError(
                    {"student_profile": "An enrolment number is required for students."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password", "") or get_random_string(14)
        profiles = {
            key: validated_data.pop(key, None)
            for key in ("student_profile", "faculty_profile", "scholar_profile", "alumni_profile")
        }
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        self._sync_profiles(user, profiles)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        profiles = {
            key: validated_data.pop(key, None)
            for key in ("student_profile", "faculty_profile", "scholar_profile", "alumni_profile")
        }
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
            instance.must_change_password = True
        instance.save()
        self._sync_profiles(instance, profiles)
        return instance

    def _sync_profiles(self, user, profiles):
        mapping = {
            "student_profile": (StudentProfile, "student_profile"),
            "faculty_profile": (FacultyProfile, "faculty_profile"),
            "scholar_profile": (ScholarProfile, "scholar_profile"),
            "alumni_profile": (AlumniProfile, "alumni_profile"),
        }
        for key, data in profiles.items():
            if not data:
                continue
            model, accessor = mapping[key]
            existing = getattr(user, accessor, None)
            if existing:
                for field, value in data.items():
                    setattr(existing, field, value)
                existing.save()
            else:
                model.objects.create(user=user, **data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Your current password is incorrect."})
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "The new password must differ from the current one."}
            )
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        password_validation.validate_password(value)
        return value


class PreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["theme_preference", "locale", "timezone_name", "phone", "bio", "avatar"]


class RolePermissionSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = RolePermission
        fields = ["id", "role", "permission_code", "is_granted", "label"]

    def get_label(self, obj):
        return PERMISSION_LABELS.get(obj.permission_code, obj.permission_code)

    def validate_permission_code(self, value):
        if value not in ALL_PERMISSIONS:
            raise serializers.ValidationError("Unknown permission code '%s'." % value)
        return value
