from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.research.models import (
    ConferenceParticipation,
    Publication,
    ResearchMilestone,
    ResearchProject,
)


class ResearchMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchMilestone
        fields = [
            "id", "project", "title", "description", "due_date", "completed_on", "status",
            "display_order",
        ]
        read_only_fields = ["id"]


class ResearchProjectSerializer(serializers.ModelSerializer):
    pi_detail = UserBriefSerializer(source="principal_investigator", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    milestones = ResearchMilestoneSerializer(many=True, read_only=True)
    publication_count = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = ResearchProject
        fields = [
            "id", "title", "abstract", "principal_investigator", "pi_detail", "collaborators",
            "department", "department_name", "research_area", "funding_agency",
            "funding_amount", "start_date", "expected_end_date", "status",
            "dataset_references", "ethics_approval_reference", "milestones",
            "publication_count", "progress", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_publication_count(self, obj):
        return obj.publications.count()

    def get_progress(self, obj):
        milestones = list(obj.milestones.all())
        if not milestones:
            return 0
        done = sum(1 for m in milestones if m.status == ResearchMilestone.Status.COMPLETED)
        return round(done / len(milestones) * 100)

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("expected_end_date", getattr(self.instance, "expected_end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"expected_end_date": "The end date cannot precede the start date."}
            )
        return attrs


class PublicationSerializer(serializers.ModelSerializer):
    owner_detail = UserBriefSerializer(source="owner", read_only=True)
    type_display = serializers.CharField(source="get_publication_type_display", read_only=True)
    project_title = serializers.CharField(source="project.title", read_only=True, default="")

    class Meta:
        model = Publication
        fields = [
            "id", "title", "authors", "owner", "owner_detail", "project", "project_title",
            "venue", "publication_type", "type_display", "year", "doi", "url", "abstract",
            "citation_count", "status", "document", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_year(self, value):
        from django.utils import timezone

        if value and (value < 1900 or value > timezone.now().year + 2):
            raise serializers.ValidationError("Enter a realistic publication year.")
        return value


class ConferenceSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    role_display = serializers.CharField(source="get_participation_role_display", read_only=True)

    class Meta:
        model = ConferenceParticipation
        fields = [
            "id", "user", "user_name", "name", "organiser", "location", "start_date",
            "end_date", "participation_role", "role_display", "paper_title",
        ]
        read_only_fields = ["id"]
