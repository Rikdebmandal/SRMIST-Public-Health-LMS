from rest_framework import serializers

from apps.academics.models import (
    AcademicSession,
    Batch,
    CurriculumItem,
    Department,
    Holiday,
    Program,
    Semester,
)


class DepartmentSerializer(serializers.ModelSerializer):
    hod_name = serializers.CharField(source="hod.full_name", read_only=True, default="")
    program_count = serializers.IntegerField(read_only=True, default=0)
    member_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Department
        fields = [
            "id", "name", "code", "description", "hod", "hod_name", "email", "phone",
            "established_year", "is_active", "program_count", "member_count", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProgramSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    student_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Program
        fields = [
            "id", "name", "code", "department", "department_name", "level", "level_display",
            "duration_years", "total_semesters", "total_credits", "description", "is_active",
            "student_count",
        ]
        read_only_fields = ["id"]


class AcademicSessionSerializer(serializers.ModelSerializer):
    semester_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = AcademicSession
        fields = [
            "id", "name", "start_date", "end_date", "is_current", "is_active", "semester_count",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": "The end date must be after the start date."})
        return attrs


class SemesterSerializer(serializers.ModelSerializer):
    session_name = serializers.CharField(source="session.name", read_only=True)

    class Meta:
        model = Semester
        fields = [
            "id", "session", "session_name", "number", "name", "start_date", "end_date",
            "exam_start_date", "exam_end_date", "is_current", "result_published",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": "The end date must be after the start date."})
        exam_start = attrs.get("exam_start_date", getattr(self.instance, "exam_start_date", None))
        exam_end = attrs.get("exam_end_date", getattr(self.instance, "exam_end_date", None))
        if exam_start and exam_end and exam_end < exam_start:
            raise serializers.ValidationError(
                {"exam_end_date": "The examination end date must not precede its start date."}
            )
        return attrs


class BatchSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name", read_only=True)
    student_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Batch
        fields = [
            "id", "program", "program_name", "name", "start_year", "end_year",
            "current_semester", "is_active", "student_count",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start = attrs.get("start_year", getattr(self.instance, "start_year", None))
        end = attrs.get("end_year", getattr(self.instance, "end_year", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_year": "The end year cannot precede the start year."})
        return attrs


class CurriculumItemSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = CurriculumItem
        fields = [
            "id", "program", "program_name", "batch", "semester_number", "course",
            "course_code", "course_name", "credits", "category", "category_display",
            "is_mandatory", "prerequisites", "display_order",
        ]
        read_only_fields = ["id"]


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "session", "name", "date", "end_date", "is_working_day"]
        read_only_fields = ["id"]
