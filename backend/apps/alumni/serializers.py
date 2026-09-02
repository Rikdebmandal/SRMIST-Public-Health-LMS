from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.alumni.models import JobPosting, MentorshipRequest


class MentorshipRequestSerializer(serializers.ModelSerializer):
    requester_detail = UserBriefSerializer(source="requester", read_only=True)
    mentor_detail = UserBriefSerializer(source="mentor", read_only=True)

    class Meta:
        model = MentorshipRequest
        fields = [
            "id", "requester", "requester_detail", "mentor", "mentor_detail", "topic",
            "message", "status", "responded_at", "response_note", "created_at",
        ]
        read_only_fields = ["id", "requester", "responded_at", "created_at", "status"]

    def validate_mentor(self, value):
        request = self.context.get("request")
        if request and value.pk == request.user.pk:
            raise serializers.ValidationError("You cannot request mentorship from yourself.")
        profile = getattr(value, "alumni_profile", None)
        if profile is not None and not profile.is_available_for_mentorship:
            raise serializers.ValidationError("This mentor is not currently accepting requests.")
        return value


class JobPostingSerializer(serializers.ModelSerializer):
    posted_by_detail = UserBriefSerializer(source="posted_by", read_only=True)
    type_display = serializers.CharField(source="get_opportunity_type_display", read_only=True)
    mode_display = serializers.CharField(source="get_work_mode_display", read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = JobPosting
        fields = [
            "id", "title", "organization", "opportunity_type", "type_display", "work_mode",
            "mode_display", "location", "description", "eligibility", "skills_required",
            "stipend_or_salary", "application_url", "contact_email", "deadline",
            "posted_by", "posted_by_detail", "status", "view_count", "is_open", "created_at",
        ]
        read_only_fields = ["id", "posted_by", "view_count", "created_at"]

    def validate_deadline(self, value):
        from django.utils import timezone

        if value and not self.instance and value < timezone.localdate():
            raise serializers.ValidationError("The deadline cannot be in the past.")
        return value
