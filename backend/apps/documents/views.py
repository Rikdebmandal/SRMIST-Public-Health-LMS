from django.db.models import F, Q
from django.http import FileResponse, Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm, Roles, teaches_section
from apps.core.viewsets import AuditedModelViewSet
from apps.courses.models import Course, CourseSection, Enrollment
from apps.documents.models import Note, NoteAccessLog, NoteVersion
from apps.documents.serializers import (
    NoteSerializer,
    NoteUploadSerializer,
    NoteVersionSerializer,
)


class NoteViewSet(AuditedModelViewSet):
    queryset = Note.objects.select_related("course", "department", "created_by").prefetch_related(
        "versions"
    )
    serializer_class = NoteSerializer
    required_permission = Perm.NOTE_VIEW
    required_write_permission = Perm.NOTE_MANAGE
    filterset_fields = ["course", "section", "department", "semester_number", "visibility", "is_published"]
    search_fields = ["title", "description", "topic"]
    ordering_fields = ["created_at", "title", "download_count"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    audit_object_type = "note"
    # Declared so per-action throttle scopes are accepted as initkwargs.
    throttle_scope = None
    # Recording a view is a reader action, not an authoring one.
    action_permissions = {"register_view": Perm.NOTE_VIEW}

    def get_queryset(self):
        """Visibility is enforced here - a student can never list a note they
        are not entitled to, so search cannot leak unauthorised resources."""
        qs = super().get_queryset()
        user = self.request.user
        if user.has_perm_code(Perm.NOTE_MANAGE) and user.role in (Roles.ADMIN, Roles.DEAN):
            return qs
        if user.role in (Roles.FACULTY, Roles.SCHOLAR):
            return qs.filter(
                Q(created_by=user)
                | Q(section__faculty_assignments__faculty=user)
                | Q(department=user.department)
            ).distinct()

        enrolled_sections = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list("section_id", flat=True)
        enrolled_courses = Enrollment.objects.filter(
            student=user, status=Enrollment.Status.ACTIVE
        ).values_list("section__course_id", flat=True)
        return qs.filter(is_published=True).filter(
            Q(visibility=Note.Visibility.INSTITUTION)
            | Q(visibility=Note.Visibility.DEPARTMENT, department=user.department)
            | Q(visibility=Note.Visibility.COURSE, course_id__in=enrolled_courses)
            | Q(visibility=Note.Visibility.SECTION, section_id__in=enrolled_sections)
            | Q(visibility=Note.Visibility.SECTION, section__isnull=True, course_id__in=enrolled_courses)
        ).distinct()

    @action(detail=False, methods=["post"], url_path="upload", throttle_scope="upload")
    def upload(self, request):
        """Create a note plus its first version from a multipart payload."""
        if not request.user.has_perm_code(Perm.NOTE_MANAGE):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot upload notes."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = NoteUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        course = Course.objects.filter(pk=data["course"]).select_related("department").first()
        if course is None:
            return Response(
                {"error": {"code": "not_found", "message": "Course not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        section = None
        if data.get("section"):
            section = CourseSection.objects.filter(pk=data["section"]).first()
            if section and not teaches_section(request.user, section):
                return Response(
                    {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                    status=status.HTTP_403_FORBIDDEN,
                )

        tags = [tag.strip() for tag in (data.get("tags") or "").split(",") if tag.strip()]
        note = Note.objects.create(
            title=data["title"],
            description=data.get("description", ""),
            course=course,
            section=section,
            department=course.department,
            semester_number=data.get("semester_number", course.semester_number),
            topic=data.get("topic", ""),
            tags=tags,
            visibility=data["visibility"],
            allow_download=data["allow_download"],
            created_by=request.user,
            updated_by=request.user,
        )
        uploaded = data["file"]
        NoteVersion.objects.create(
            note=note,
            version_number=1,
            file=uploaded,
            original_filename=uploaded.name[:255],
            file_size=uploaded.size,
            content_type=getattr(uploaded, "content_type", "")[:100],
            changelog=data.get("changelog", "Initial upload"),
            created_by=request.user,
        )
        audit.record(
            AuditAction.FILE_UPLOAD,
            obj=note,
            description="Uploaded note '%s'" % note.title,
            metadata={"size": uploaded.size, "filename": uploaded.name},
        )
        return Response(
            NoteSerializer(note, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="versions", throttle_scope="upload")
    def add_version(self, request, pk=None):
        note = self.get_object()
        if not request.user.has_perm_code(Perm.NOTE_MANAGE):
            return Response(
                {"error": {"code": "permission_denied", "message": "You cannot update this note."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = NoteVersionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data["file"]
        next_number = (note.versions.count() or 0) + 1
        note.versions.update(is_active=False)
        version = NoteVersion.objects.create(
            note=note,
            version_number=next_number,
            file=uploaded,
            original_filename=uploaded.name[:255],
            file_size=uploaded.size,
            content_type=getattr(uploaded, "content_type", "")[:100],
            changelog=serializer.validated_data.get("changelog", ""),
            is_active=True,
            created_by=request.user,
        )
        audit.record(AuditAction.FILE_UPLOAD, obj=note, description="Added version %s" % next_number)
        return Response(NoteVersionSerializer(version).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        note = self.get_object()
        return Response(
            NoteVersionSerializer(note.versions.order_by("-version_number"), many=True).data
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Serve the active version - permission checked via get_queryset."""
        note = self.get_object()
        if not note.allow_download and not request.user.has_perm_code(Perm.NOTE_MANAGE):
            return Response(
                {"error": {"code": "permission_denied", "message": "Downloads are disabled for this resource."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        version = note.active_version
        if version is None or not version.file:
            raise Http404("No file is attached to this note.")

        Note.objects.filter(pk=note.pk).update(download_count=F("download_count") + 1)
        NoteAccessLog.objects.create(note=note, user=request.user, action="DOWNLOAD")
        audit.record(AuditAction.EXPORT, obj=note, description="Downloaded note")
        return FileResponse(
            version.file.open("rb"),
            as_attachment=True,
            filename=version.original_filename or version.file.name.split("/")[-1],
        )

    @action(detail=True, methods=["post"], url_path="view")
    def register_view(self, request, pk=None):
        note = self.get_object()
        Note.objects.filter(pk=note.pk).update(view_count=F("view_count") + 1)
        NoteAccessLog.objects.create(note=note, user=request.user, action="VIEW")
        return Response({"detail": "recorded"})
