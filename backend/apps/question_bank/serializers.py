from rest_framework import serializers

from apps.question_bank.models import Question, QuestionOption, QuestionTopic


class QuestionTopicSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    full_path = serializers.CharField(read_only=True)
    question_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = QuestionTopic
        fields = [
            "id", "course", "course_code", "name", "parent", "description", "display_order",
            "full_path", "question_count",
        ]
        read_only_fields = ["id"]


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text", "is_correct", "display_order"]
        read_only_fields = ["id"]


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, required=False)
    course_code = serializers.CharField(source="course.code", read_only=True)
    topic_name = serializers.CharField(source="topic.name", read_only=True, default="")
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    type_display = serializers.CharField(source="get_question_type_display", read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "course", "course_code", "topic", "topic_name", "text", "question_type",
            "type_display", "difficulty", "marks", "correct_answer", "explanation", "tags",
            "status", "times_used", "options", "created_by_name", "created_at",
        ]
        read_only_fields = ["id", "times_used", "created_at"]

    def validate(self, attrs):
        question_type = attrs.get("question_type", getattr(self.instance, "question_type", None))
        options = attrs.get("options") or self.initial_data.get("options") or []
        objective = question_type in (
            Question.QuestionType.MCQ,
            Question.QuestionType.MULTI,
            Question.QuestionType.TRUE_FALSE,
        )
        if objective and not self.instance and len(options) < 2:
            raise serializers.ValidationError(
                {"options": "Objective questions need at least two options."}
            )
        if objective and options:
            correct = [item for item in options if item.get("is_correct")]
            if not correct:
                raise serializers.ValidationError(
                    {"options": "Mark at least one option as correct."}
                )
            if question_type == Question.QuestionType.MCQ and len(correct) > 1:
                raise serializers.ValidationError(
                    {"options": "A single-answer question can have only one correct option."}
                )
        return attrs

    def create(self, validated_data):
        options = validated_data.pop("options", [])
        question = Question.objects.create(**validated_data)
        for index, option in enumerate(options):
            QuestionOption.objects.create(
                question=question, display_order=option.get("display_order", index), **{
                    key: value for key, value in option.items() if key != "display_order"
                }
            )
        return question

    def update(self, instance, validated_data):
        options = validated_data.pop("options", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if options is not None:
            instance.options.all().delete()
            for index, option in enumerate(options):
                QuestionOption.objects.create(
                    question=instance, display_order=option.get("display_order", index), **{
                        key: value for key, value in option.items() if key != "display_order"
                    }
                )
        return instance
