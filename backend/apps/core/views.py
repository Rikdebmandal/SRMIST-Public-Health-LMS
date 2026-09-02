"""Cross-cutting endpoints: global search, exports and the health check."""
import csv
import io

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditlogs import services as audit
from apps.auditlogs.models import AuditAction
from apps.core.permissions import Perm, Roles, teaches_section


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.db import connection

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database = "ok"
        except Exception:
            database = "unavailable"
        return Response({"status": "ok", "database": database, "api_version": "v1"})


class GlobalSearchView(APIView):
    """Search across everything the caller is entitled to see.

    Each source reuses its own viewset queryset logic, so a user can never
    discover a resource through search that they could not open directly.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"query": query, "results": [], "total": 0})

        user = request.user
        results = []

        from apps.alumni.models import JobPosting
        from apps.announcements.models import Announcement
        from apps.calendarapp.models import CalendarEvent
        from apps.courses.models import Course, Enrollment
        from apps.documents.models import Note
        from apps.library.models import ResourceLink
        from apps.question_bank.models import Question
        from apps.research.models import Publication

        # Courses
        courses = Course.objects.filter(Q(code__icontains=query) | Q(name__icontains=query))
        if user.role == Roles.STUDENT:
            courses = courses.filter(sections__enrollments__student=user).distinct()
        elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
            courses = courses.filter(
                Q(sections__faculty_assignments__faculty=user) | Q(department=user.department)
            ).distinct()
        elif user.role == Roles.ADMIN and user.department_id:
            courses = courses.filter(department=user.department)
        results.extend(
            {
                "type": "course",
                "id": str(item.id),
                "title": "%s - %s" % (item.code, item.name),
                "subtitle": item.department.name,
                "link": "/courses/%s" % item.id,
            }
            for item in courses[:8]
        )

        # Notes - reuse the visibility rules from the notes viewset
        if user.has_perm_code(Perm.NOTE_VIEW):
            enrolled_sections = Enrollment.objects.filter(
                student=user, status=Enrollment.Status.ACTIVE
            ).values_list("section_id", flat=True)
            enrolled_courses = Enrollment.objects.filter(
                student=user, status=Enrollment.Status.ACTIVE
            ).values_list("section__course_id", flat=True)
            notes = Note.objects.filter(
                Q(title__icontains=query) | Q(topic__icontains=query) | Q(description__icontains=query)
            )
            if user.role in (Roles.ADMIN, Roles.DEAN):
                pass
            elif user.role in (Roles.FACULTY, Roles.SCHOLAR):
                notes = notes.filter(
                    Q(created_by=user)
                    | Q(section__faculty_assignments__faculty=user)
                    | Q(department=user.department)
                ).distinct()
            else:
                notes = notes.filter(is_published=True).filter(
                    Q(visibility=Note.Visibility.INSTITUTION)
                    | Q(visibility=Note.Visibility.DEPARTMENT, department=user.department)
                    | Q(visibility=Note.Visibility.COURSE, course_id__in=enrolled_courses)
                    | Q(visibility=Note.Visibility.SECTION, section_id__in=enrolled_sections)
                ).distinct()
            results.extend(
                {
                    "type": "note",
                    "id": str(item.id),
                    "title": item.title,
                    "subtitle": "%s - %s" % (item.course.code, item.topic or "Notes"),
                    "link": "/notes?highlight=%s" % item.id,
                }
                for item in notes[:8]
            )

        # Announcements
        announcements = Announcement.objects.filter(
            Q(title__icontains=query) | Q(body__icontains=query),
            status=Announcement.Status.PUBLISHED,
        )
        results.extend(
            {
                "type": "announcement",
                "id": str(item.id),
                "title": item.title,
                "subtitle": item.get_priority_display(),
                "link": "/announcements/%s" % item.id,
            }
            for item in announcements[:20]
            if item.visible_to(user)
        )

        # Question bank
        if user.has_perm_code(Perm.QUESTION_VIEW) and user.role != Roles.STUDENT:
            questions = Question.objects.filter(text__icontains=query)
            if user.role in (Roles.FACULTY, Roles.SCHOLAR):
                questions = questions.filter(
                    Q(created_by=user) | Q(course__department=user.department)
                ).distinct()
            results.extend(
                {
                    "type": "question",
                    "id": str(item.id),
                    "title": item.text[:80],
                    "subtitle": "%s - %s" % (item.course.code, item.get_difficulty_display()),
                    "link": "/question-bank?highlight=%s" % item.id,
                }
                for item in questions[:6]
            )

        # Events, jobs, publications, e-resources
        results.extend(
            {
                "type": "event",
                "id": str(item.id),
                "title": item.title,
                "subtitle": item.start_at.strftime("%d %b %Y"),
                "link": "/calendar",
            }
            for item in CalendarEvent.objects.filter(
                Q(title__icontains=query) | Q(description__icontains=query), is_published=True
            )[:5]
        )
        if user.has_perm_code(Perm.JOB_VIEW):
            results.extend(
                {
                    "type": "job",
                    "id": str(item.id),
                    "title": item.title,
                    "subtitle": item.organization,
                    "link": "/jobs/%s" % item.id,
                }
                for item in JobPosting.objects.filter(
                    Q(title__icontains=query) | Q(organization__icontains=query),
                    status=JobPosting.Status.PUBLISHED,
                )[:5]
            )
        if user.has_perm_code(Perm.RESEARCH_VIEW):
            results.extend(
                {
                    "type": "publication",
                    "id": str(item.id),
                    "title": item.title[:80],
                    "subtitle": item.venue or item.get_publication_type_display(),
                    "link": "/research/publications",
                }
                for item in Publication.objects.filter(
                    Q(title__icontains=query) | Q(authors__icontains=query)
                )[:5]
            )
        results.extend(
            {
                "type": "resource",
                "id": str(item.id),
                "title": item.title,
                "subtitle": item.category.name if item.category else "E-resource",
                "link": "/library",
            }
            for item in ResourceLink.objects.filter(
                Q(title__icontains=query) | Q(description__icontains=query), is_active=True
            )[:5]
        )

        return Response({"query": query, "total": len(results), "results": results})


class ExportViewSet(viewsets.ViewSet):
    """CSV exports. Access control runs before a single row is written."""

    permission_classes = [IsAuthenticated]

    def _csv_response(self, filename, header, rows):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        writer.writerows(rows)
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="%s"' % filename
        return response

    @action(detail=False, methods=["get"], url_path="attendance/(?P<section_id>[^/.]+)")
    def attendance(self, request, section_id=None):
        from apps.attendance.models import AttendancePolicy, AttendanceRecord
        from apps.attendance.services import summarise
        from apps.courses.models import CourseSection, Enrollment

        if not request.user.has_perm_code(Perm.REPORT_EXPORT):
            return Response(
                {"error": {"code": "permission_denied", "message": "Exports are restricted."}},
                status=403,
            )
        section = CourseSection.objects.filter(pk=section_id).select_related("course").first()
        if section is None:
            return Response({"error": {"code": "not_found", "message": "Section not found."}}, status=404)
        if not teaches_section(request.user, section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=403,
            )

        policy = AttendancePolicy.resolve_for(section.course.department)
        rows = []
        for enrollment in section.enrollments.filter(
            status=Enrollment.Status.ACTIVE
        ).select_related("student", "student__student_profile"):
            summary = summarise(
                AttendanceRecord.objects.filter(
                    student=enrollment.student, session__section=section
                ),
                policy,
            )
            rows.append(
                [
                    getattr(
                        getattr(enrollment.student, "student_profile", None),
                        "enrollment_number",
                        "",
                    ),
                    enrollment.student.full_name,
                    summary["total"],
                    summary["present"],
                    summary["absent"],
                    summary["late"],
                    summary["excused"],
                    summary["percentage"],
                    summary["status"],
                ]
            )
        audit.record(
            AuditAction.EXPORT,
            obj=section,
            description="Exported attendance report",
            metadata={"rows": len(rows)},
        )
        return self._csv_response(
            "attendance-%s-%s.csv" % (section.course.code, section.name),
            [
                "Enrolment number", "Student", "Total sessions", "Present", "Absent", "Late",
                "Excused", "Attendance %", "Status",
            ],
            rows,
        )

    @action(detail=False, methods=["get"], url_path="gradebook/(?P<section_id>[^/.]+)")
    def gradebook(self, request, section_id=None):
        from apps.assessments.services import gradebook
        from apps.courses.models import CourseSection

        if not request.user.has_perm_code(Perm.REPORT_EXPORT):
            return Response(
                {"error": {"code": "permission_denied", "message": "Exports are restricted."}},
                status=403,
            )
        section = CourseSection.objects.filter(pk=section_id).select_related("course").first()
        if section is None:
            return Response({"error": {"code": "not_found", "message": "Section not found."}}, status=404)
        if not teaches_section(request.user, section):
            return Response(
                {"error": {"code": "permission_denied", "message": "You are not assigned to this section."}},
                status=403,
            )

        data = gradebook(section)
        header = ["Enrolment number", "Student"] + [
            "%s (/%s)" % (component["name"], component["max_marks"])
            for component in data["components"]
        ] + ["Internal", "External", "Total", "Percentage", "Grade", "Grade point"]
        rows = []
        for student in data["students"]:
            row = [student["enrollment_number"], student["full_name"]]
            row.extend(
                cell["marks_obtained"] if cell["marks_obtained"] is not None else ""
                for cell in student["cells"]
            )
            row.extend(
                [
                    student["internal_total"],
                    student["external_total"],
                    student["total_marks"],
                    student["percentage"],
                    student["grade_letter"],
                    student["grade_point"],
                ]
            )
            rows.append(row)

        audit.record(
            AuditAction.EXPORT,
            obj=section,
            description="Exported gradebook",
            metadata={"rows": len(rows)},
        )
        return self._csv_response(
            "gradebook-%s-%s.csv" % (section.course.code, section.name), header, rows
        )

    @action(detail=False, methods=["get"], url_path="students")
    def students(self, request):
        from apps.accounts.models import User

        if not request.user.has_perm_code(Perm.USER_VIEW) or not request.user.has_perm_code(
            Perm.REPORT_EXPORT
        ):
            return Response(
                {"error": {"code": "permission_denied", "message": "Exports are restricted."}},
                status=403,
            )
        students = User.objects.filter(role=Roles.STUDENT).select_related(
            "student_profile", "department", "student_profile__program"
        )
        if request.user.role == Roles.ADMIN and request.user.department_id:
            students = students.filter(department=request.user.department)
        rows = [
            [
                getattr(getattr(student, "student_profile", None), "enrollment_number", ""),
                student.full_name,
                student.email,
                student.department.name if student.department else "",
                getattr(
                    getattr(getattr(student, "student_profile", None), "program", None), "name", ""
                ),
                getattr(getattr(student, "student_profile", None), "current_semester", ""),
                "Active" if student.is_active else "Inactive",
            ]
            for student in students
        ]
        audit.record(
            AuditAction.EXPORT, description="Exported student list", metadata={"rows": len(rows)}
        )
        return self._csv_response(
            "students.csv",
            ["Enrolment number", "Name", "Email", "Department", "Program", "Semester", "Status"],
            rows,
        )

    @action(detail=False, methods=["get"], url_path="at-risk")
    def at_risk(self, request):
        from apps.analytics.services import at_risk_students

        if not request.user.has_perm_code(Perm.RISK_VIEW):
            return Response(
                {"error": {"code": "permission_denied", "message": "Risk data is restricted."}},
                status=403,
            )
        department = request.user.department if request.user.role == Roles.ADMIN else None
        results = at_risk_students(department=department, limit=200)
        rows = [
            [
                item["student"]["enrollment_number"],
                item["student"]["full_name"],
                item["score"],
                item["level_label"],
                "; ".join(factor["label"] for factor in item["factors"]),
            ]
            for item in results
        ]
        audit.record(
            AuditAction.EXPORT,
            description="Exported academic support risk list",
            metadata={"rows": len(rows)},
        )
        return self._csv_response(
            "academic-support-indicators.csv",
            ["Enrolment number", "Student", "Score", "Level", "Contributing factors"],
            rows,
        )
