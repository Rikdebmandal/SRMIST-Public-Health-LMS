from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.forums.models import ContentReport, DiscussionReply, DiscussionThread


class DiscussionReplySerializer(serializers.ModelSerializer):
    author_detail = UserBriefSerializer(source="author", read_only=True)
    has_voted = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionReply
        fields = [
            "id", "thread", "author", "author_detail", "parent", "body",
            "is_accepted_answer", "is_hidden", "helpful_count", "has_voted", "created_at",
        ]
        read_only_fields = [
            "id", "author", "helpful_count", "is_accepted_answer", "is_hidden", "created_at",
        ]

    def get_has_voted(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.votes.filter(user=request.user).exists()

    def validate_body(self, value):
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Write a longer reply.")
        return value


class DiscussionThreadSerializer(serializers.ModelSerializer):
    author_detail = UserBriefSerializer(source="author", read_only=True)
    course_code = serializers.CharField(source="section.course.code", read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = [
            "id", "section", "course_code", "author", "author_detail", "title", "body",
            "tags", "status", "is_pinned", "view_count", "reply_count", "replies",
            "created_at",
        ]
        read_only_fields = [
            "id", "author", "view_count", "reply_count", "is_pinned", "created_at",
        ]

    def get_replies(self, obj):
        if self.context.get("include_replies"):
            replies = obj.replies.filter(is_hidden=False).select_related("author")
            return DiscussionReplySerializer(replies, many=True, context=self.context).data
        return None

    def validate_title(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Give the question a clearer title.")
        return value


class ContentReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source="reporter.full_name", read_only=True)

    class Meta:
        model = ContentReport
        fields = [
            "id", "thread", "reply", "reporter", "reporter_name", "reason", "status",
            "resolution_note", "created_at",
        ]
        read_only_fields = ["id", "reporter", "created_at"]

    def validate(self, attrs):
        if not attrs.get("thread") and not attrs.get("reply"):
            raise serializers.ValidationError("Report either a thread or a reply.")
        return attrs
