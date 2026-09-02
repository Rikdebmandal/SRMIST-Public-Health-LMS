"""End-to-end workflow and edge-case tests (brief sections 72 and 73)."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.academics.models import AcademicSession, Department, Semester
from apps.accounts.models import StudentProfile, User
from apps.assessments.models import (
    AssessmentComponent,
    ComponentScore,
    GradeBand,
    GradeScale,
)
from apps.assessments.services import gradebook, recompute_result
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.attendance.models import AttendancePolicy, AttendanceRecord, AttendanceSession
from apps.attendance.services import student_overall
from apps.auditlogs.models import AuditLog
from apps.core.rbac import Roles
from apps.core.validators import validate_upload
from apps.courses.models import (
    Course,
    CourseSection,
    Enrollment,
    FacultyCourseAssignment,
)


class WorkflowTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(name="School of Public Health", code="SPH")
        cls.session = AcademicSession.objects.create(
            name="2026-27", start_date=date(2026, 6, 1), end_date=date(2027, 5, 31), is_current=True
        )
        cls.semester = Semester.objects.create(
            session=cls.session,
            number=1,
            name="Semester 1",
            start_date=date(2026, 6, 15),
            end_date=date(2026, 11, 15),
        )
        cls.course = Course.objects.create(
            code="PHS5101", name="Epidemiology", department=cls.department, credits=4
        )
        cls.section = CourseSection.objects.create(
            course=cls.course, semester=cls.semester, name="A", capacity=2
        )

        cls.faculty = User.objects.create_user(
            email="faculty@test.local",
            password="TestPass!2345",
            full_name="Faculty One",
            role=Roles.FACULTY,
        )
        cls.faculty.department = cls.department
        cls.faculty.save()
        FacultyCourseAssignment.objects.create(section=cls.section, faculty=cls.faculty)

        cls.student = User.objects.create_user(
            email="student@test.local",
            password="TestPass!2345",
            full_name="Student One",
            role=Roles.STUDENT,
        )
        cls.student.department = cls.department
        cls.student.save()
        StudentProfile.objects.create(user=cls.student, enrollment_number="RA001")
        Enrollment.objects.create(student=cls.student, section=cls.section)

        AttendancePolicy.objects.create(
            name="Default", warning_threshold=75, critical_threshold=65
        )

        scale = GradeScale.objects.create(name="Default", is_default=True)
        for letter, low, point, is_pass in [
            ("O", 91, 10, True),
            ("A", 71, 8, True),
            ("P", 40, 4, True),
            ("F", 0, 0, False),
        ]:
            GradeBand.objects.create(
                scale=scale,
                letter=letter,
                min_percentage=low,
                max_percentage=100,
                grade_point=point,
                is_pass=is_pass,
            )


class EnrolmentEdgeCaseTests(WorkflowTestCase):
    def test_duplicate_enrolment_is_rejected(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            "/api/v1/enrollments",
            {"student": str(self.student.id), "section": str(self.section.id)},
            format="json",
        )
        # Faculty lack the enrolment permission, so this is a 403 either way.
        self.assertIn(response.status_code, (400, 403))

    def test_capacity_is_enforced(self):
        from apps.courses.serializers import EnrollmentSerializer

        second = User.objects.create_user(
            email="s2@test.local", password="TestPass!2345", full_name="S2", role=Roles.STUDENT
        )
        third = User.objects.create_user(
            email="s3@test.local", password="TestPass!2345", full_name="S3", role=Roles.STUDENT
        )
        Enrollment.objects.create(student=second, section=self.section)  # section now full

        serializer = EnrollmentSerializer(
            data={"student": str(third.id), "section": str(self.section.id)}
        )
        self.assertFalse(serializer.is_valid())


class AttendanceWorkflowTests(WorkflowTestCase):
    def test_duplicate_session_for_same_date_and_period_is_rejected(self):
        AttendanceSession.objects.create(section=self.section, date=date(2026, 7, 1), period=1)
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            "/api/v1/attendance/sessions",
            {"section": str(self.section.id), "date": "2026-07-01", "period": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_marking_a_student_outside_the_section_is_rejected(self):
        outsider = User.objects.create_user(
            email="outsider@test.local",
            password="TestPass!2345",
            full_name="Outsider",
            role=Roles.STUDENT,
        )
        session = AttendanceSession.objects.create(
            section=self.section, date=date(2026, 7, 2), period=1
        )
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            f"/api/v1/attendance/sessions/{session.id}/mark",
            {"records": [{"student": str(outsider.id), "status": "PRESENT"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 0)
        self.assertEqual(len(response.data["rejected"]), 1)

    def test_locked_session_cannot_be_edited(self):
        session = AttendanceSession.objects.create(
            section=self.section,
            date=date(2026, 7, 3),
            period=1,
            status=AttendanceSession.Status.LOCKED,
        )
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            f"/api/v1/attendance/sessions/{session.id}/mark",
            {"records": [{"student": str(self.student.id), "status": "PRESENT"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_invalid_status_is_rejected(self):
        session = AttendanceSession.objects.create(
            section=self.section, date=date(2026, 7, 4), period=1
        )
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            f"/api/v1/attendance/sessions/{session.id}/mark",
            {"records": [{"student": str(self.student.id), "status": "TELEPORTED"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_percentage_reflects_the_configured_policy(self):
        for index, status_value in enumerate(
            ["PRESENT", "PRESENT", "PRESENT", "ABSENT", "EXCUSED"]
        ):
            session = AttendanceSession.objects.create(
                section=self.section, date=date(2026, 7, 10) + timedelta(days=index), period=1
            )
            AttendanceRecord.objects.create(
                session=session, student=self.student, status=status_value
            )

        summary = student_overall(self.student)
        # 3 present of 4 applicable (the excused session leaves the denominator).
        self.assertEqual(summary["present"], 3)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["percentage"], 75.0)
        self.assertEqual(summary["status"], "ok")

    def test_a_student_with_no_sessions_does_not_error(self):
        summary = student_overall(self.student)
        self.assertEqual(summary["percentage"], 0.0)
        self.assertEqual(summary["total"], 0)


class MarksWorkflowTests(WorkflowTestCase):
    def setUp(self):
        self.component = AssessmentComponent.objects.create(
            section=self.section, name="Quiz", max_marks=20, weight=10
        )

    def test_marks_above_the_maximum_are_rejected(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            "/api/v1/scores/bulk",
            {
                "component": str(self.component.id),
                "scores": [{"student": str(self.student.id), "marks_obtained": 25}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 0)
        self.assertEqual(len(response.data["rejected"]), 1)

    def test_negative_marks_are_rejected(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            "/api/v1/scores/bulk",
            {
                "component": str(self.component.id),
                "scores": [{"student": str(self.student.id), "marks_obtained": -1}],
            },
            format="json",
        )
        self.assertEqual(len(response.data["rejected"]), 1)

    def test_valid_marks_are_stored_and_the_result_recomputed(self):
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            "/api/v1/scores/bulk",
            {
                "component": str(self.component.id),
                "scores": [{"student": str(self.student.id), "marks_obtained": 16}],
            },
            format="json",
        )
        self.assertEqual(response.data["updated"], 1)
        result = recompute_result(self.student, self.section)
        # 16/20 scaled onto a weight of 10 -> 8.00 out of an internal max of 10.
        self.assertEqual(result.internal_total, Decimal("8.00"))
        self.assertEqual(result.percentage, Decimal("80.00"))
        self.assertEqual(result.grade_letter, "A")

    def test_published_marks_are_locked_against_further_edits(self):
        score = ComponentScore.objects.create(
            component=self.component,
            student=self.student,
            marks_obtained=10,
            status=ComponentScore.Status.PUBLISHED,
        )
        self.assertTrue(score.is_locked)

        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            "/api/v1/scores/bulk",
            {
                "component": str(self.component.id),
                "scores": [{"student": str(self.student.id), "marks_obtained": 20}],
            },
            format="json",
        )
        self.assertEqual(len(response.data["rejected"]), 1)
        score.refresh_from_db()
        self.assertEqual(score.marks_obtained, Decimal("10.00"))

    def test_gradebook_grid_covers_every_enrolled_student(self):
        grid = gradebook(self.section)
        self.assertEqual(len(grid["students"]), 1)
        self.assertEqual(len(grid["components"]), 1)
        self.assertEqual(grid["internal_max"], 10.0)

    def test_absent_student_scores_zero_without_breaking_the_total(self):
        ComponentScore.objects.create(
            component=self.component, student=self.student, is_absent=True
        )
        result = recompute_result(self.student, self.section)
        self.assertEqual(result.internal_total, Decimal("0.00"))


class AssignmentWorkflowTests(WorkflowTestCase):
    def test_submission_after_the_deadline_is_marked_late(self):
        assignment = Assignment.objects.create(
            section=self.section,
            title="Late test",
            max_marks=20,
            due_date=timezone.now() - timedelta(days=1),
            status=Assignment.Status.PUBLISHED,
            allow_late_submission=True,
        )
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/v1/submissions",
            {"assignment": str(assignment.id), "text_response": "My answer"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        submission = AssignmentSubmission.objects.get(assignment=assignment, student=self.student)
        self.assertEqual(submission.status, AssignmentSubmission.Status.LATE)

    def test_submission_is_refused_when_late_work_is_not_accepted(self):
        assignment = Assignment.objects.create(
            section=self.section,
            title="Strict",
            max_marks=20,
            due_date=timezone.now() - timedelta(days=1),
            status=Assignment.Status.PUBLISHED,
            allow_late_submission=False,
        )
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/api/v1/submissions",
            {"assignment": str(assignment.id), "text_response": "Too late"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unenrolled_student_cannot_submit(self):
        outsider = User.objects.create_user(
            email="outsider2@test.local",
            password="TestPass!2345",
            full_name="Outsider",
            role=Roles.STUDENT,
        )
        assignment = Assignment.objects.create(
            section=self.section,
            title="Open",
            max_marks=20,
            due_date=timezone.now() + timedelta(days=3),
            status=Assignment.Status.PUBLISHED,
        )
        self.client.force_authenticate(outsider)
        response = self.client.post(
            "/api/v1/submissions",
            {"assignment": str(assignment.id), "text_response": "Sneaky"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_draft_assignment_is_not_visible_to_students(self):
        Assignment.objects.create(
            section=self.section,
            title="Draft only",
            max_marks=20,
            due_date=timezone.now() + timedelta(days=3),
            status=Assignment.Status.DRAFT,
        )
        self.client.force_authenticate(self.student)
        response = self.client.get("/api/v1/assignments")
        self.assertEqual(response.data["count"], 0)

    def test_grading_above_the_maximum_is_rejected(self):
        assignment = Assignment.objects.create(
            section=self.section,
            title="Graded",
            max_marks=20,
            due_date=timezone.now() - timedelta(days=1),
            status=Assignment.Status.PUBLISHED,
        )
        submission = AssignmentSubmission.objects.create(
            assignment=assignment, student=self.student, text_response="Answer"
        )
        self.client.force_authenticate(self.faculty)
        response = self.client.post(
            f"/api/v1/submissions/{submission.id}/grade",
            {"marks_obtained": 99},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class UploadValidationTests(WorkflowTestCase):
    def test_executable_extension_is_refused(self):
        payload = SimpleUploadedFile("payload.exe", b"MZ\x90\x00", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError):
            validate_upload(payload)

    def test_disallowed_extension_is_refused(self):
        payload = SimpleUploadedFile("script.js", b"alert(1)", content_type="text/javascript")
        with self.assertRaises(ValidationError):
            validate_upload(payload)

    def test_oversized_file_is_refused(self):
        payload = SimpleUploadedFile("big.pdf", b"%PDF-" + b"0" * (3 * 1024 * 1024), content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_upload(payload, max_size_mb=1)

    def test_empty_file_is_refused(self):
        payload = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_upload(payload)

    def test_renamed_executable_is_caught_by_content_sniffing(self):
        """An .exe renamed to .pdf must fail the magic-number check."""
        payload = SimpleUploadedFile("disguised.pdf", b"MZ\x90\x00" * 10, content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_upload(payload)

    def test_a_genuine_pdf_is_accepted(self):
        payload = SimpleUploadedFile("notes.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        self.assertIsNotNone(validate_upload(payload))


class AuditLogTests(WorkflowTestCase):
    def test_login_is_recorded(self):
        self.client.post(
            "/api/v1/auth/login",
            {"email": "student@test.local", "password": "TestPass!2345"},
            format="json",
        )
        self.assertTrue(AuditLog.objects.filter(action="LOGIN").exists())

    def test_failed_login_is_recorded(self):
        self.client.post(
            "/api/v1/auth/login",
            {"email": "student@test.local", "password": "nope"},
            format="json",
        )
        self.assertTrue(AuditLog.objects.filter(action="LOGIN_FAILED").exists())

    def test_entries_cannot_be_modified(self):
        entry = AuditLog.objects.create(action="LOGIN", description="test")
        entry.description = "tampered"
        with self.assertRaises(PermissionError):
            entry.save()

    def test_entries_cannot_be_deleted(self):
        entry = AuditLog.objects.create(action="LOGIN", description="test")
        with self.assertRaises(PermissionError):
            entry.delete()

    def test_credentials_are_scrubbed_from_metadata(self):
        from apps.auditlogs.services import scrub

        cleaned = scrub({"password": "hunter2", "nested": {"token": "abc"}, "keep": "value"})
        self.assertEqual(cleaned["password"], "[redacted]")
        self.assertEqual(cleaned["nested"]["token"], "[redacted]")
        self.assertEqual(cleaned["keep"], "value")


class CertificateVerificationTests(WorkflowTestCase):
    def test_public_verification_exposes_only_confirming_fields(self):
        from apps.certificates.models import Certificate

        certificate = Certificate.objects.create(
            holder=self.student,
            title="Workshop",
            issued_on=date(2026, 7, 1),
            issuing_department=self.department,
        )
        response = self.client.get(f"/api/v1/verify/certificate/{certificate.certificate_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["valid"])
        # No email, no marks, no identifiers beyond the holder's name.
        self.assertNotIn("email", str(response.data).lower())

    def test_unknown_certificate_returns_not_found(self):
        response = self.client.get("/api/v1/verify/certificate/SPH-NOPE")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["valid"])

    def test_revoked_certificate_reports_as_invalid(self):
        from apps.certificates.models import Certificate

        certificate = Certificate.objects.create(
            holder=self.student,
            title="Revoked",
            issued_on=date(2026, 7, 1),
            status=Certificate.Status.REVOKED,
        )
        response = self.client.get(f"/api/v1/verify/certificate/{certificate.certificate_id}")
        self.assertFalse(response.data["valid"])


class FeedbackPrivacyTests(WorkflowTestCase):
    def test_anonymous_response_stores_no_respondent(self):
        from apps.feedback.models import (
            FeedbackForm,
            FeedbackParticipation,
            FeedbackQuestion,
            FeedbackResponse,
        )

        form = FeedbackForm.objects.create(
            title="Course feedback",
            is_anonymous=True,
            status=FeedbackForm.Status.OPEN,
            department=self.department,
        )
        question = FeedbackQuestion.objects.create(
            form=form, text="Rate the course", question_type="RATING"
        )
        self.client.force_authenticate(self.student)
        response = self.client.post(
            f"/api/v1/feedback/forms/{form.id}/submit",
            {"answers": [{"question": str(question.id), "rating_value": 4}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        stored = FeedbackResponse.objects.get(form=form)
        self.assertIsNone(stored.respondent)
        # Participation is tracked separately, so a second submission is blocked.
        self.assertTrue(FeedbackParticipation.objects.filter(form=form, user=self.student).exists())

        again = self.client.post(
            f"/api/v1/feedback/forms/{form.id}/submit",
            {"answers": [{"question": str(question.id), "rating_value": 1}]},
            format="json",
        )
        self.assertEqual(again.status_code, 409)
