from django.db.models import Count, Q
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import Perm, Roles
from apps.core.viewsets import AuditedModelViewSet
from apps.research.models import (
    ConferenceParticipation,
    Publication,
    ResearchMilestone,
    ResearchProject,
)
from apps.research.serializers import (
    ConferenceSerializer,
    PublicationSerializer,
    ResearchMilestoneSerializer,
    ResearchProjectSerializer,
)


class ResearchProjectViewSet(AuditedModelViewSet):
    queryset = ResearchProject.objects.select_related(
        "principal_investigator", "department"
    ).prefetch_related("milestones", "collaborators")
    serializer_class = ResearchProjectSerializer
    required_permission = Perm.RESEARCH_VIEW
    required_write_permission = Perm.RESEARCH_MANAGE
    filterset_fields = ["department", "status", "principal_investigator"]
    search_fields = ["title", "abstract", "research_area", "funding_agency"]
    audit_object_type = "research project"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Roles.SCHOLAR:
            return qs.filter(
                Q(principal_investigator=user)
                | Q(collaborators=user)
                | Q(department=user.department)
            ).distinct()
        return qs

    def perform_create(self, serializer):
        if not serializer.validated_data.get("principal_investigator"):
            serializer.validated_data["principal_investigator"] = self.request.user
        return super().perform_create(serializer)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        qs = self.get_queryset().filter(
            Q(principal_investigator=request.user) | Q(collaborators=request.user)
        ).distinct()
        return Response(ResearchProjectSerializer(qs, many=True).data)


class ResearchMilestoneViewSet(AuditedModelViewSet):
    queryset = ResearchMilestone.objects.select_related("project").all()
    serializer_class = ResearchMilestoneSerializer
    required_permission = Perm.RESEARCH_VIEW
    required_write_permission = Perm.RESEARCH_MANAGE
    filterset_fields = ["project", "status"]
    pagination_class = None
    audit_object_type = "research milestone"


class PublicationViewSet(AuditedModelViewSet):
    queryset = Publication.objects.select_related("owner", "project").all()
    serializer_class = PublicationSerializer
    required_permission = Perm.RESEARCH_VIEW
    required_write_permission = Perm.RESEARCH_MANAGE
    filterset_fields = ["owner", "publication_type", "year", "status", "project"]
    search_fields = ["title", "authors", "venue", "doi"]
    ordering_fields = ["year", "citation_count", "created_at"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    audit_object_type = "publication"

    def perform_create(self, serializer):
        if not serializer.validated_data.get("owner"):
            serializer.validated_data["owner"] = self.request.user
        return super().perform_create(serializer)

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        qs = self.get_queryset()
        return Response(
            {
                "total": qs.count(),
                "by_year": list(
                    qs.exclude(year__isnull=True)
                    .values("year")
                    .annotate(count=Count("id"))
                    .order_by("year")
                ),
                "by_type": list(qs.values("publication_type").annotate(count=Count("id"))),
                "total_citations": sum(qs.values_list("citation_count", flat=True)),
            }
        )


class ConferenceViewSet(AuditedModelViewSet):
    queryset = ConferenceParticipation.objects.select_related("user").all()
    serializer_class = ConferenceSerializer
    required_permission = Perm.RESEARCH_VIEW
    required_write_permission = Perm.RESEARCH_MANAGE
    filterset_fields = ["user", "participation_role"]
    search_fields = ["name", "organiser", "paper_title"]
    audit_object_type = "conference"

    def perform_create(self, serializer):
        if not serializer.validated_data.get("user"):
            serializer.validated_data["user"] = self.request.user
        return super().perform_create(serializer)
