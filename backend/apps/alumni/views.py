from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.alumni.models import JobPosting, MentorshipRequest
from apps.alumni.serializers import JobPostingSerializer, MentorshipRequestSerializer
from apps.core.permissions import Perm
from apps.core.viewsets import AuditedModelViewSet
from apps.notifications.services import notify


class MentorshipRequestViewSet(AuditedModelViewSet):
    queryset = MentorshipRequest.objects.select_related("requester", "mentor").all()
    serializer_class = MentorshipRequestSerializer
    required_permission = Perm.MENTORSHIP_PARTICIPATE
    required_write_permission = Perm.MENTORSHIP_PARTICIPATE
    filterset_fields = ["status", "mentor", "requester"]
    audit_object_type = "mentorship request"

    def get_queryset(self):
        """Only the two parties to a request can ever see it."""
        user = self.request.user
        return super().get_queryset().filter(Q(requester=user) | Q(mentor=user))

    def perform_create(self, serializer):
        instance = serializer.save(
            requester=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )
        notify(
            [instance.mentor],
            event="MENTORSHIP_REQUEST",
            title="New mentorship request",
            body="%s would like guidance on: %s" % (instance.requester.full_name, instance.topic),
            link="/mentorship",
        )
        return instance

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        instance = self.get_object()
        if instance.mentor_id != request.user.pk:
            return Response(
                {"error": {"code": "permission_denied", "message": "Only the mentor can respond."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        decision = request.data.get("status")
        if decision not in (
            MentorshipRequest.Status.ACCEPTED,
            MentorshipRequest.Status.DECLINED,
            MentorshipRequest.Status.COMPLETED,
        ):
            return Response(
                {"error": {"code": "validation_error", "message": "Choose accept, decline or complete."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.status = decision
        instance.response_note = request.data.get("note", "")[:2000]
        instance.responded_at = timezone.now()
        instance.save(update_fields=["status", "response_note", "responded_at", "updated_at"])
        notify(
            [instance.requester],
            event="MENTORSHIP_REQUEST",
            title="Mentorship request %s" % decision.lower(),
            body=instance.response_note or "Your mentor has responded to your request.",
            link="/mentorship",
        )
        return Response(MentorshipRequestSerializer(instance).data)


class JobPostingViewSet(AuditedModelViewSet):
    queryset = JobPosting.objects.select_related("posted_by").all()
    serializer_class = JobPostingSerializer
    required_permission = Perm.JOB_VIEW
    required_write_permission = Perm.JOB_MANAGE
    filterset_fields = ["opportunity_type", "work_mode", "status"]
    search_fields = ["title", "organization", "description", "location"]
    ordering_fields = ["created_at", "deadline"]
    audit_object_type = "job posting"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.has_perm_code(Perm.JOB_MANAGE):
            return qs.filter(status=JobPosting.Status.PUBLISHED)
        return qs.filter(
            Q(status=JobPosting.Status.PUBLISHED) | Q(posted_by=user)
        ).distinct()

    def perform_create(self, serializer):
        return serializer.save(
            posted_by=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        JobPosting.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["get"])
    def open(self, request):
        today = timezone.localdate()
        qs = self.get_queryset().filter(status=JobPosting.Status.PUBLISHED).filter(
            Q(deadline__isnull=True) | Q(deadline__gte=today)
        )
        page = self.paginate_queryset(qs)
        serializer = JobPostingSerializer(page or qs, many=True)
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)
