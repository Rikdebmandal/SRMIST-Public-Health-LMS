from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.assessments.models import (
    AssessmentComponent,
    ComponentScore,
    CourseResult,
    ExternalMark,
    GradeBand,
    GradeScale,
)


class GradeBandSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeBand
        fields = [
            "id", "scale", "letter", "min_percentage", "max_percentage", "grade_point",
            "description", "is_pass",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        low = attrs.get("min_percentage", getattr(self.instance, "min_percentage", None))
        high = attrs.get("max_percentage", getattr(self.instance, "max_percentage", None))
        if low is not None and high is not None and high < low:
            raise serializers.ValidationError(
                {"max_percentage": "The upper bound must be at or above the lower bound."}
            )
        return attrs


class GradeScaleSerializer(serializers.ModelSerializer):
    bands = GradeBandSerializer(many=True, read_only=True)

    class Meta:
        model = GradeScale
        fields = ["id", "name", "description", "department", "is_default", "is_active", "bands"]
        read_only_fields = ["id"]


class AssessmentComponentSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="section.course.code", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    graded_count = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentComponent
        fields = [
            "id", "section", "course_code", "name", "kind", "kind_display", "max_marks",
            "weight", "is_auto_calculated", "display_order", "is_active", "graded_count",
        ]
        read_only_fields = ["id"]

    def get_graded_count(self, obj):
        return obj.scores.filter(marks_obtained__isnull=False).count()

    def validate_max_marks(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum marks must be greater than zero.")
        return value


class ComponentScoreSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)
    max_marks = serializers.DecimalField(
        source="component.max_marks", max_digits=6, decimal_places=2, read_only=True
    )

    class Meta:
        model = ComponentScore
        fields = [
            "id", "component", "component_name", "max_marks", "student", "student_detail",
            "marks_obtained", "is_absent", "remarks", "status", "published_at",
        ]
        read_only_fields = ["id", "published_at"]

    def validate(self, attrs):
        component = attrs.get("component", getattr(self.instance, "component", None))
        marks = attrs.get("marks_obtained", getattr(self.instance, "marks_obtained", None))
        if component and marks is not None:
            if marks < 0:
                raise serializers.ValidationError({"marks_obtained": "Marks cannot be negative."})
            if marks > component.max_marks:
                raise serializers.ValidationError(
                    {"marks_obtained": "Marks cannot exceed the component maximum of %s." % component.max_marks}
                )
        if self.instance and self.instance.is_locked:
            raise serializers.ValidationError(
                "These marks are published and locked. A correction requires the publish permission."
            )
        return attrs


class BulkScoreSerializer(serializers.Serializer):
    component = serializers.UUIDField()
    scores = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class ExternalMarkSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    course_code = serializers.CharField(source="section.course.code", read_only=True)

    class Meta:
        model = ExternalMark
        fields = [
            "id", "student", "student_detail", "section", "course_code", "kind",
            "marks_obtained", "max_marks", "status", "exam_date",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        obtained = attrs.get("marks_obtained", getattr(self.instance, "marks_obtained", None))
        maximum = attrs.get("max_marks", getattr(self.instance, "max_marks", None))
        if obtained is not None and obtained < 0:
            raise serializers.ValidationError({"marks_obtained": "Marks cannot be negative."})
        if obtained is not None and maximum is not None and obtained > maximum:
            raise serializers.ValidationError(
                {"marks_obtained": "Marks cannot exceed the maximum of %s." % maximum}
            )
        return attrs


class CourseResultSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    course_code = serializers.CharField(source="section.course.code", read_only=True)
    course_name = serializers.CharField(source="section.course.name", read_only=True)

    class Meta:
        model = CourseResult
        fields = [
            "id", "student", "student_detail", "section", "course_code", "course_name",
            "internal_total", "internal_max", "external_total", "external_max", "total_marks",
            "percentage", "grade_letter", "grade_point", "credits", "is_pass", "is_published",
            "computed_at",
        ]
        read_only_fields = fields
