from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.courses.models import (
    Course,
    CourseSection,
    CourseType,
    Enrollment,
    FacultyCourseAssignment,
)


class CourseTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseType
        fields = ["id", "name", "code", "description", "display_order", "is_active"]
        read_only_fields = ["id"]


class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True, default="")
    course_type_name = serializers.CharField(source="course_type.name", read_only=True, default="")
    coordinator_detail = UserBriefSerializer(source="coordinator", read_only=True)
    section_count = serializers.IntegerField(read_only=True, default=0)
    enrolled_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Course
        fields = [
            "id", "code", "name", "description", "credits", "department", "department_name",
            "department_code", "program", "program_name", "semester_number", "course_type",
            "course_type_name", "coordinator", "coordinator_detail", "syllabus",
            "learning_outcomes", "status", "section_count", "enrolled_count", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_credits(self, value):
        if value <= 0:
            raise serializers.ValidationError("Credits must be greater than zero.")
        return value


class FacultyAssignmentSerializer(serializers.ModelSerializer):
    faculty_detail = UserBriefSerializer(source="faculty", read_only=True)
    section_label = serializers.CharField(source="section.__str__", read_only=True)
    role_display = serializers.CharField(source="get_assignment_role_display", read_only=True)

    class Meta:
        model = FacultyCourseAssignment
        fields = [
            "id", "section", "section_label", "faculty", "faculty_detail", "assignment_role",
            "role_display", "is_primary", "is_active", "assigned_on",
        ]
        read_only_fields = ["id", "assigned_on"]


class CourseSectionSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    course_credits = serializers.DecimalField(
        source="course.credits", max_digits=4, decimal_places=1, read_only=True
    )
    semester_name = serializers.CharField(source="semester.name", read_only=True)
    session_name = serializers.CharField(source="semester.session.name", read_only=True)
    batch_name = serializers.CharField(source="batch.name", read_only=True, default="")
    department_id = serializers.UUIDField(source="course.department_id", read_only=True)
    faculty = serializers.SerializerMethodField()
    enrolled_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CourseSection
        fields = [
            "id", "course", "course_code", "course_name", "course_credits", "semester",
            "semester_name", "session_name", "batch", "batch_name", "department_id", "name",
            "capacity", "room", "schedule", "is_active", "faculty", "enrolled_count",
        ]
        read_only_fields = ["id"]

    def get_faculty(self, obj):
        assignments = obj.faculty_assignments.filter(is_active=True).select_related("faculty")
        return [
            {
                "id": str(item.faculty_id),
                "full_name": item.faculty.full_name,
                "role": item.assignment_role,
                "is_primary": item.is_primary,
            }
            for item in assignments
        ]

    def validate(self, attrs):
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", None))
        if capacity is not None and capacity <= 0:
            raise serializers.ValidationError({"capacity": "Capacity must be at least 1."})
        return attrs


class EnrollmentSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    course_code = serializers.CharField(source="section.course.code", read_only=True)
    course_name = serializers.CharField(source="section.course.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    enrollment_number = serializers.CharField(
        source="student.student_profile.enrollment_number", read_only=True, default=""
    )

    class Meta:
        model = Enrollment
        fields = [
            "id", "student", "student_detail", "enrollment_number", "section", "course_code",
            "course_name", "section_name", "status", "enrolled_on", "completed_on",
        ]
        read_only_fields = ["id", "enrolled_on"]

    def validate(self, attrs):
        student = attrs.get("student", getattr(self.instance, "student", None))
        section = attrs.get("section", getattr(self.instance, "section", None))
        if student and section:
            duplicate = Enrollment.objects.filter(student=student, section=section)
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    "This student is already enrolled in that section."
                )
            active = section.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
            if not self.instance and active >= section.capacity:
                raise serializers.ValidationError(
                    "This section is full (capacity %s)." % section.capacity
                )
        return attrs


class BulkEnrollSerializer(serializers.Serializer):
    section = serializers.UUIDField()
    students = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
