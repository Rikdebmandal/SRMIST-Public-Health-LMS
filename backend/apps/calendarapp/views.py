from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.calendarapp.models import CalendarEvent, EventRegistration
from apps.calendarapp.serializers import CalendarEventSerializer, EventRegistrationSerializer
from apps.core.permissions import Perm, Roles
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Enrollment


class CalendarEventViewSet(AuditedModelViewSet):
    queryset = CalendarEvent.objects.select_related(
        "department", "section__course", "created_by"
    ).prefetch_related("registrations")
    serializer_class = CalendarEventSerializer
    required_permission = Perm.EVENT_VIEW
    required_write_permission = Perm.EVENT_MANAGE
    filterset_fields = ["category", "audience", "department", "section", "is_published"]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["start_at"]
    audit_object_type = "calendar event"
    # Attendees register for events they cannot edit.
    action_permissions = {
        "register": Perm.EVENT_VIEW,
        "cancel_registration": Perm.EVENT_VIEW,
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role in (Roles.ADMIN, Roles.DEAN) and user.has_perm_code(Perm.EVENT_MANAGE):
            return qs

        role_ids = [
            row_id
            for row_id, roles in qs.filter(
                audience=CalendarEvent.Audience.ROLE
            ).values_list("id", "target_roles")
            if user.role in (roles or [])
        ]
        section_ids = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list("section_id", flat=True)
        taught_ids = user.course_assignments.filter(is_active=True).values_list(
            "section_id", flat=True
        )

        return qs.filter(is_published=True).filter(
            Q(audience=CalendarEvent.Audience.INSTITUTION)
            | Q(audience=CalendarEvent.Audience.DEPARTMENT, department=user.department)
            | Q(id__in=role_ids)
            | Q(audience=CalendarEvent.Audience.SECTION, section_id__in=section_ids)
            | Q(audience=CalendarEvent.Audience.SECTION, section_id__in=taught_ids)
            | Q(owner=user)
            | Q(created_by=user)
        ).distinct()

    def perform_create(self, serializer):
        audience = serializer.validated_data.get("audience")
        if audience == CalendarEvent.Audience.PERSONAL:
            return serializer.save(
                owner=self.request.user,
                created_by=self.request.user,
                updated_by=self.request.user,
            )
        return super().perform_create(serializer)

    @action(detail=False, methods=["get"])
    def agenda(self, request):
        """Unified feed: stored events plus projected deadlines and exams."""
        from apps.academics.models import Holiday, Semester
        from apps.assignments.models import Assignment

        start_raw = request.query_params.get("from")
        end_raw = request.query_params.get("to")
        now = timezone.now()
        start = (
            timezone.make_aware(datetime.combine(datetime.fromisoformat(start_raw).date(), time.min))
            if start_raw
            else now - timezone.timedelta(days=7)
        )
        end = (
            timezone.make_aware(datetime.combine(datetime.fromisoformat(end_raw).date(), time.max))
            if end_raw
            else now + timezone.timedelta(days=60)
        )

        items = [
            {
                "id": str(event.id),
                "title": event.title,
                "category": event.category,
                "start_at": event.start_at.isoformat(),
                "end_at": event.end_at.isoformat() if event.end_at else None,
                "all_day": event.all_day,
                "location": event.location,
                "source": "event",
                "link": "/calendar",
            }
            for event in self.get_queryset().filter(start_at__gte=start, start_at__lte=end)
        ]

        user = request.user
        if user.role == Roles.STUDENT:
            section_ids = Enrollment.objects.filter(
                student=user, status=Enrollment.Status.ACTIVE
            ).values_list("section_id", flat=True)
        else:
            section_ids = user.course_assignments.filter(is_active=True).values_list(
                "section_id", flat=True
            )

        assignments = Assignment.objects.filter(
            section_id__in=section_ids,
            status=Assignment.Status.PUBLISHED,
            due_date__gte=start,
            due_date__lte=end,
        ).select_related("section__course")
        items.extend(
            {
                "id": "assignment-%s" % item.id,
                "title": "Due: %s" % item.title,
                "category": "ASSIGNMENT",
                "start_at": item.due_date.isoformat(),
                "end_at": None,
                "all_day": False,
                "location": item.section.course.code,
                "source": "assignment",
                "link": "/assignments/%s" % item.id,
            }
            for item in assignments
        )

        semesters = Semester.objects.filter(
            exam_start_date__isnull=False,
            exam_start_date__gte=start.date(),
            exam_start_date__lte=end.date(),
        ).select_related("session")
        items.extend(
            {
                "id": "exam-%s" % semester.id,
                "title": "Examinations - %s" % semester.name,
                "category": "EXAMINATION",
                "start_at": timezone.make_aware(
                    datetime.combine(semester.exam_start_date, time(9, 0))
                ).isoformat(),
                "end_at": timezone.make_aware(
                    datetime.combine(semester.exam_end_date or semester.exam_start_date, time(17, 0))
                ).isoformat(),
                "all_day": True,
                "location": "",
                "source": "exam",
                "link": "/calendar",
            }
            for semester in semesters
        )

        holidays = Holiday.objects.filter(date__gte=start.date(), date__lte=end.date())
        items.extend(
            {
                "id": "holiday-%s" % holiday.id,
                "title": holiday.name,
                "category": "HOLIDAY",
                "start_at": timezone.make_aware(
                    datetime.combine(holiday.date, time.min)
                ).isoformat(),
                "end_at": None,
                "all_day": True,
                "location": "",
                "source": "holiday",
                "link": "/calendar",
            }
            for holiday in holidays
        )

        items.sort(key=lambda entry: entry["start_at"])
        return Response({"from": start.date().isoformat(), "to": end.date().isoformat(), "items": items})

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        event = self.get_object()
        registration, created = EventRegistration.objects.get_or_create(
            event=event, user=request.user
        )
        if not created and registration.status == EventRegistration.Status.CANCELLED:
            registration.status = EventRegistration.Status.REGISTERED
            registration.save(update_fields=["status", "updated_at"])
        return Response(EventRegistrationSerializer(registration).data)

    @action(detail=True, methods=["post"], url_path="cancel-registration")
    def cancel_registration(self, request, pk=None):
        event = self.get_object()
        registration = EventRegistration.objects.filter(event=event, user=request.user).first()
        if registration:
            registration.status = EventRegistration.Status.CANCELLED
            registration.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Registration cancelled."})
