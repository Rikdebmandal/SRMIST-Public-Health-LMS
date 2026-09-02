from rest_framework import serializers

from apps.feedback.models import (
    FeedbackAnswer,
    FeedbackForm,
    FeedbackQuestion,
    FeedbackResponse,
)


class FeedbackQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackQuestion
        fields = [
            "id", "form", "text", "question_type", "choices", "scale_min", "scale_max",
            "is_required", "display_order",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        question_type = attrs.get("question_type", getattr(self.instance, "question_type", None))
        choices = attrs.get("choices", getattr(self.instance, "choices", None)) or []
        if question_type in (
            FeedbackQuestion.QuestionType.CHOICE,
            FeedbackQuestion.QuestionType.MULTI_CHOICE,
        ) and len(choices) < 2:
            raise serializers.ValidationError({"choices": "Provide at least two choices."})
        low = attrs.get("scale_min", getattr(self.instance, "scale_min", 1))
        high = attrs.get("scale_max", getattr(self.instance, "scale_max", 5))
        if question_type == FeedbackQuestion.QuestionType.RATING and high <= low:
            raise serializers.ValidationError({"scale_max": "The scale maximum must exceed the minimum."})
        return attrs


class FeedbackFormSerializer(serializers.ModelSerializer):
    questions = FeedbackQuestionSerializer(many=True, read_only=True)
    response_count = serializers.SerializerMethodField()
    has_responded = serializers.SerializerMethodField()
    course_code = serializers.CharField(source="section.course.code", read_only=True, default="")

    class Meta:
        model = FeedbackForm
        fields = [
            "id", "title", "description", "form_type", "is_anonymous", "section",
            "course_code", "department", "target_roles", "opens_at", "closes_at", "status",
            "questions", "response_count", "has_responded", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_response_count(self, obj):
        return obj.responses.count()

    def get_has_responded(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.participations.filter(user=request.user).exists()


class FeedbackAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackAnswer
        fields = ["id", "question", "rating_value", "text_value", "choice_value"]
        read_only_fields = ["id"]


class FeedbackSubmissionSerializer(serializers.Serializer):
    form = serializers.UUIDField()
    answers = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class FeedbackResponseSerializer(serializers.ModelSerializer):
    answers = FeedbackAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = FeedbackResponse
        fields = ["id", "form", "submitted_at", "answers"]
        read_only_fields = fields
