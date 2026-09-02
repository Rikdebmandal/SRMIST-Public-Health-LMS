from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.announcements.models import Announcement, AnnouncementCategory, AnnouncementRead
from apps.announcements.serializers import (
    AnnouncementCategorySerializer,
    AnnouncementSerializer,
)
from apps.core.permissions import Perm, Roles
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Enrollment
from apps.notifications.services import notify


class AnnouncementCategoryViewSet(AuditedModelViewSet):
    queryset = AnnouncementCategory.objects.all()
    serializer_class = AnnouncementCategorySerializer
    required_permission = Perm.ANNOUNCEMENT_VIEW
    required_write_permission = Perm.SETTINGS_MANAGE
    pagination_class = None
    audit_object_type = "announcement category"


class AnnouncementViewSet(AuditedModelViewSet):
    queryset = Announcement.objects.select_related(
        "category", "department", "course", "created_by"
    ).prefetch_related("target_users", "reads")
    serializer_class = AnnouncementSerializer
    required_permission = Perm.ANNOUNCEMENT_VIEW
    required_write_permission = Perm.ANNOUNCEMENT_MANAGE
    filterset_fields = ["priority", "audience", "status", "department", "course"]
    search_fields = ["title", "body"]
    ordering_fields = ["publish_at", "priority"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    audit_object_type = "announcement"
    # Any recipient can mark a notice read; only authors publish.
    action_permissions = {"mark_read": Perm.ANNOUNCEMENT_VIEW}

    def get_queryset(self):
        """Audience targeting is applied in SQL so nothing leaks through search."""
        qs = super().get_queryset()
        user = self.request.user
        if user.has_perm_code(Perm.ANNOUNCEMENT_MANAGE) and self.request.query_params.get("mine") == "true":
            return qs.filter(created_by=user)
        if user.role in (Roles.ADMIN, Roles.DEAN) and user.has_perm_code(Perm.ANNOUNCEMENT_MANAGE):
            return qs

        now = timezone.now()
        enrolled_sections = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list("section_id", flat=True)
        enrolled_courses = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list("section__course_id", flat=True)

        # JSONField `contains` is not portable to SQLite, so role targeting is
        # resolved to a small id set first and folded back into the query.
        role_ids = [
            row_id
            for row_id, roles in qs.filter(
                audience=Announcement.Audience.ROLE
            ).values_list("id", "target_roles")
            if user.role in (roles or [])
        ]

        visible = (
            Q(audience=Announcement.Audience.INSTITUTION)
            | Q(audience=Announcement.Audience.SCHOOL)
            | Q(audience=Announcement.Audience.DEPARTMENT, department=user.department)
            | Q(id__in=role_ids)
            | Q(audience=Announcement.Audience.INDIVIDUAL, target_users=user)
            | Q(audience=Announcement.Audience.COURSE, course_id__in=enrolled_courses)
            | Q(audience=Announcement.Audience.SECTION, section_id__in=enrolled_sections)
            | Q(created_by=user)
        )
        return (
            qs.filter(status=Announcement.Status.PUBLISHED, publish_at__lte=now)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .filter(visible)
            .distinct()
        )

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        announcement = self.get_object()
        announcement.status = Announcement.Status.PUBLISHED
        if announcement.publish_at > timezone.now():
            announcement.publish_at = timezone.now()
        announcement.save(update_fields=["status", "publish_at", "updated_at"])

        recipients = self._resolve_recipients(announcement)
        notify(
            recipients,
            event="ANNOUNCEMENT",
            title=announcement.title,
            body=announcement.body[:400],
            link="/announcements/%s" % announcement.id,
            level="CRITICAL" if announcement.priority == "URGENT" else "INFO",
        )
        return Response(
            AnnouncementSerializer(announcement, context={"request": request}).data
        )

    def _resolve_recipients(self, announcement):
        from apps.accounts.models import User

        if announcement.audience in (
            Announcement.Audience.INSTITUTION,
            Announcement.Audience.SCHOOL,
        ):
            return list(User.objects.filter(is_active=True))
        if announcement.audience == Announcement.Audience.DEPARTMENT:
            return list(User.objects.filter(is_active=True, department=announcement.department))
        if announcement.audience == Announcement.Audience.ROLE:
            return list(User.objects.filter(is_active=True, role__in=announcement.target_roles or []))
        if announcement.audience == Announcement.Audience.INDIVIDUAL:
            return list(announcement.target_users.all())
        if announcement.audience == Announcement.Audience.COURSE:
            return [
                enrollment.student
                for enrollment in Enrollment.objects.filter(
                    section__course=announcement.course, status=Enrollment.Status.ACTIVE
                ).select_related("student")
            ]
        if announcement.audience == Announcement.Audience.SECTION:
            return [
                enrollment.student
                for enrollment in Enrollment.objects.filter(
                    section=announcement.section, status=Enrollment.Status.ACTIVE
                ).select_related("student")
            ]
        return []

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        announcement = self.get_object()
        AnnouncementRead.objects.get_or_create(announcement=announcement, user=request.user)
        return Response({"detail": "marked as read"})

    @action(detail=False, methods=["get"])
    def feed(self, request):
        """The live feed used by dashboards - pinned first, then newest."""
        items = self.get_queryset().order_by("-is_pinned", "-publish_at")[:10]
        return Response(
            AnnouncementSerializer(items, many=True, context={"request": request}).data
        )
