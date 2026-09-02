from django.db.models import F, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import Perm, Roles, teaches_section
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Enrollment
from apps.forums.models import ContentReport, DiscussionReply, DiscussionThread, ReplyVote
from apps.forums.serializers import (
    ContentReportSerializer,
    DiscussionReplySerializer,
    DiscussionThreadSerializer,
)
from apps.notifications.services import notify


def accessible_section_ids(user):
    """Sections the user may discuss in: enrolled as a student, or teaching."""
    enrolled = Enrollment.objects.filter(
        student=user, status=Enrollment.Status.ACTIVE
    ).values_list("section_id", flat=True)
    taught = user.course_assignments.filter(is_active=True).values_list("section_id", flat=True)
    return list(enrolled) + list(taught)


class DiscussionThreadViewSet(AuditedModelViewSet):
    queryset = DiscussionThread.objects.select_related(
        "author", "section__course"
    ).prefetch_related("replies__author")
    serializer_class = DiscussionThreadSerializer
    required_permission = Perm.FORUM_PARTICIPATE
    required_write_permission = Perm.FORUM_PARTICIPATE
    filterset_fields = ["section", "status"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "reply_count"]
    audit_object_type = "discussion thread"

    def get_queryset(self):
        qs = super().get_queryset().exclude(status=DiscussionThread.Status.HIDDEN)
        user = self.request.user
        if user.role in (Roles.ADMIN, Roles.DEAN):
            return super().get_queryset()
        return qs.filter(section_id__in=accessible_section_ids(user))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_replies"] = self.action == "retrieve"
        return context

    def perform_create(self, serializer):
        section = serializer.validated_data["section"]
        if section.id not in accessible_section_ids(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have access to this course discussion.")
        return serializer.save(
            author=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        DiscussionThread.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"], url_path="pin")
    def pin(self, request, pk=None):
        if not request.user.has_perm_code(Perm.FORUM_MODERATE):
            return Response(
                {"error": {"code": "permission_denied", "message": "Moderator access required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        thread = self.get_object()
        thread.is_pinned = not thread.is_pinned
        thread.save(update_fields=["is_pinned", "updated_at"])
        return Response(DiscussionThreadSerializer(thread, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="hide")
    def hide(self, request, pk=None):
        if not request.user.has_perm_code(Perm.FORUM_MODERATE):
            return Response(
                {"error": {"code": "permission_denied", "message": "Moderator access required."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        thread = self.get_object()
        thread.status = DiscussionThread.Status.HIDDEN
        thread.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Thread hidden."})


class DiscussionReplyViewSet(AuditedModelViewSet):
    queryset = DiscussionReply.objects.select_related("author", "thread__section__course").all()
    serializer_class = DiscussionReplySerializer
    required_permission = Perm.FORUM_PARTICIPATE
    required_write_permission = Perm.FORUM_PARTICIPATE
    filterset_fields = ["thread", "author"]
    audit_object_type = "discussion reply"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in (Roles.ADMIN, Roles.DEAN):
            return qs
        return qs.filter(
            thread__section_id__in=accessible_section_ids(user), is_hidden=False
        )

    def perform_create(self, serializer):
        thread = serializer.validated_data["thread"]
        if thread.section_id not in accessible_section_ids(self.request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have access to this discussion.")
        if thread.status == DiscussionThread.Status.CLOSED:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("This thread is closed.")
        instance = serializer.save(
            author=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )
        DiscussionThread.objects.filter(pk=thread.pk).update(reply_count=F("reply_count") + 1)
        if thread.author_id != self.request.user.pk:
            notify(
                [thread.author],
                event="FORUM_REPLY",
                title="New reply to your question",
                body="%s replied to '%s'" % (self.request.user.full_name, thread.title),
                link="/discussions/%s" % thread.id,
            )
        return instance

    @action(detail=True, methods=["post"], url_path="helpful")
    def helpful(self, request, pk=None):
        reply = self.get_object()
        vote, created = ReplyVote.objects.get_or_create(reply=reply, user=request.user)
        if created:
            DiscussionReply.objects.filter(pk=reply.pk).update(
                helpful_count=F("helpful_count") + 1
            )
        else:
            vote.delete()
            DiscussionReply.objects.filter(pk=reply.pk).update(
                helpful_count=F("helpful_count") - 1
            )
        reply.refresh_from_db()
        return Response({"helpful_count": reply.helpful_count, "voted": created})

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        reply = self.get_object()
        thread = reply.thread
        can_accept = thread.author_id == request.user.pk or teaches_section(
            request.user, thread.section
        )
        if not can_accept:
            return Response(
                {"error": {"code": "permission_denied", "message": "Only the author or faculty can accept an answer."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        thread.replies.update(is_accepted_answer=False)
        reply.is_accepted_answer = True
        reply.save(update_fields=["is_accepted_answer", "updated_at"])
        thread.status = DiscussionThread.Status.ANSWERED
        thread.save(update_fields=["status", "updated_at"])
        return Response(DiscussionReplySerializer(reply, context={"request": request}).data)


class ContentReportViewSet(AuditedModelViewSet):
    queryset = ContentReport.objects.select_related("reporter").all()
    serializer_class = ContentReportSerializer
    required_permission = Perm.FORUM_PARTICIPATE
    required_write_permission = Perm.FORUM_PARTICIPATE
    filterset_fields = ["status"]
    audit_object_type = "content report"

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.has_perm_code(Perm.FORUM_MODERATE):
            qs = qs.filter(reporter=self.request.user)
        return qs

    def perform_create(self, serializer):
        return serializer.save(
            reporter=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )
