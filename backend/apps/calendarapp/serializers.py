from rest_framework import serializers

from apps.calendarapp.models import CalendarEvent, EventRegistration


class CalendarEventSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default="")
    course_code = serializers.CharField(source="section.course.code", read_only=True, default="")
    organiser = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    registration_count = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()

    class Meta:
        model = CalendarEvent
        fields = [
            "id", "title", "description", "category", "start_at", "end_at", "all_day",
            "location", "online_url", "audience", "department", "department_name", "section",
            "course_code", "target_roles", "owner", "is_published", "reminder_minutes",
            "organiser", "registration_count", "is_registered",
        ]
        read_only_fields = ["id"]

    def get_registration_count(self, obj):
        return obj.registrations.filter(status=EventRegistration.Status.REGISTERED).count()

    def get_is_registered(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.registrations.filter(
            user=request.user, status=EventRegistration.Status.REGISTERED
        ).exists()

    def validate(self, attrs):
        start = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_at": "The end time must be after the start."})
        return attrs


class EventRegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = EventRegistration
        fields = ["id", "event", "event_title", "user", "user_name", "status", "created_at"]
        read_only_fields = ["id", "user", "created_at"]
