"""Seed a realistic, entirely fictional demonstration dataset.

Every person in this dataset is invented. No real student information is used
(brief section 66).

    python manage.py seed_demo --reset
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.academics.models import (
    AcademicSession,
    Batch,
    CurriculumItem,
    Department,
    Holiday,
    Program,
    Semester,
)
from apps.accounts.models import (
    AlumniProfile,
    FacultyProfile,
    ScholarProfile,
    StudentProfile,
    User,
)
from apps.alumni.models import JobPosting, MentorshipRequest
from apps.analytics.models import ActivityLog, RiskRule
from apps.announcements.models import Announcement, AnnouncementCategory
from apps.assessments.models import (
    AssessmentComponent,
    ComponentScore,
    CourseResult,
    ExternalMark,
    GradeBand,
    GradeScale,
)
from apps.assessments.services import recompute_section
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.attendance.models import AttendancePolicy, AttendanceRecord, AttendanceSession
from apps.calendarapp.models import CalendarEvent
from apps.certificates.models import Certificate
from apps.core.calculations import DEFAULT_RISK_RULES
from apps.core.rbac import Roles
from apps.courses.models import (
    Course,
    CourseSection,
    CourseType,
    Enrollment,
    FacultyCourseAssignment,
)
from apps.documents.models import Note, NoteVersion
from apps.feedback.models import FeedbackForm, FeedbackQuestion
from apps.forums.models import DiscussionReply, DiscussionThread
from apps.library.models import ResourceCategory, ResourceLink
from apps.notifications.models import NotificationEvent, NotificationTemplate
from apps.question_bank.models import Question, QuestionOption, QuestionTopic
from apps.research.models import Publication, ResearchMilestone, ResearchProject
from apps.settings_app.models import DashboardWidget, SystemSetting

DEMO_PASSWORD = "Demo@12345"

FIRST_NAMES = [
    "Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Ishita", "Arjun",
    "Sneha", "Rahul", "Priya", "Karthik", "Nandini", "Aditya", "Riya", "Siddharth",
    "Tanvi", "Manish", "Pooja", "Nikhil", "Shreya", "Varun", "Lakshmi", "Harish",
    "Divya", "Sanjay", "Kavya", "Rajesh", "Anjali", "Farhan", "Neha", "Imran", "Sara",
    "Joseph", "Grace", "Thomas", "Rebecca", "Suresh", "Bhavana",
]
LAST_NAMES = [
    "Iyer", "Menon", "Sharma", "Reddy", "Nair", "Patel", "Krishnan", "Bose", "Rao",
    "Gupta", "Pillai", "Verma", "Chandran", "Joshi", "Banerjee", "Kulkarni", "Das",
    "Mahajan", "Sundaram", "Fernandes",
]


class Command(BaseCommand):
    help = "Seed the LMS with fictional demonstration data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing data first.")
        parser.add_argument("--students", type=int, default=36, help="Number of demo students.")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(20260902)
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Public Health LMS demo data"))

        if options["reset"]:
            self._reset()

        self._settings()
        self._notification_templates()
        self._risk_rules()
        department = self._department()
        program = self._program(department)
        session, semesters = self._sessions()
        batch = self._batch(program)
        staff = self._staff(department)
        courses = self._courses(department, program)
        sections = self._sections(courses, semesters, batch, staff)
        self._curriculum(program, batch, courses)
        students = self._students(department, program, batch, options["students"])
        scholars = self._scholars(department, staff)
        alumni = self._alumni(department, program)
        self._enrol(students, sections)
        self._grade_scale(department)
        self._attendance_policy(department)
        self._attendance(sections, students)
        self._assessments(sections, students)
        self._assignments(sections, students, staff)
        self._notes(courses, sections, staff)
        self._question_bank(courses, staff)
        self._announcements(department, staff, courses)
        self._calendar(department, session)
        self._forums(sections, students, staff)
        self._research(department, scholars, staff)
        self._alumni_content(alumni, students)
        self._library(department)
        self._feedback(department, sections)
        self._certificates(department, students, staff)
        self._widgets()
        self._activity(students)

        for section in sections:
            recompute_section(section)

        # The seeded component scores are already PUBLISHED, so publish the
        # derived course results too - otherwise students see no CGPA.
        CourseResult.objects.all().update(is_published=True)

        self.stdout.write(self.style.SUCCESS("\nDemo data ready."))
        self.stdout.write("\nSign in with any of these (password: %s)\n" % DEMO_PASSWORD)
        for label, email in [
            ("Dean", "dean@sph.srmist.demo"),
            ("HOD / Admin", "hod@sph.srmist.demo"),
            ("Faculty", "faculty1@sph.srmist.demo"),
            ("Research scholar", "scholar1@sph.srmist.demo"),
            ("Student", "student1@sph.srmist.demo"),
            ("Alumni", "alumni1@sph.srmist.demo"),
        ]:
            self.stdout.write("  %-18s %s" % (label, email))

    # ------------------------------------------------------------------
    def _reset(self):
        self.stdout.write("  Clearing existing data...")
        for model in [
            ActivityLog, Certificate, FeedbackQuestion, FeedbackForm, ResourceLink,
            ResourceCategory, MentorshipRequest, JobPosting, Publication,
            ResearchMilestone, ResearchProject, DiscussionReply, DiscussionThread,
            CalendarEvent, Announcement, AnnouncementCategory, QuestionOption, Question,
            QuestionTopic, NoteVersion, Note, AssignmentSubmission, Assignment,
            ComponentScore, ExternalMark, AssessmentComponent, GradeBand, GradeScale,
            AttendanceRecord, AttendanceSession, AttendancePolicy, Enrollment,
            FacultyCourseAssignment, CourseSection, CurriculumItem, Course, CourseType,
            Batch, Holiday, Semester, AcademicSession, StudentProfile, FacultyProfile,
            ScholarProfile, AlumniProfile, Program,
        ]:
            model.all_objects.all().hard_delete() if hasattr(
                model, "all_objects"
            ) else model.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Department.all_objects.all().hard_delete()

    def _settings(self):
        rows = [
            ("institution_name", "Institution name", "SRM Institute of Science and Technology", "STRING", "BRANDING", True),
            ("school_name", "School name", "School of Public Health", "STRING", "BRANDING", True),
            ("platform_name", "Platform name", "Public Health LMS", "STRING", "BRANDING", True),
            ("primary_color", "Primary colour", "#0b4f6c", "COLOR", "BRANDING", True),
            ("secondary_color", "Secondary colour", "#1c7c54", "COLOR", "BRANDING", True),
            ("logo_url", "Logo URL", "", "STRING", "BRANDING", True),
            ("footer_text", "Footer text", "Public Health LMS - School of Public Health | Academic Project - M.Sc. Health Data Science", "STRING", "BRANDING", True),
            ("support_email", "Support email", "support@sph.srmist.demo", "STRING", "GENERAL", True),
            ("default_theme", "Default theme", "system", "STRING", "BRANDING", True),
            ("attendance_warning_threshold", "Attendance warning threshold (%)", "75", "NUMBER", "ACADEMIC", False),
            ("attendance_critical_threshold", "Attendance critical threshold (%)", "65", "NUMBER", "ACADEMIC", False),
            ("passing_percentage", "Passing percentage", "40", "NUMBER", "ACADEMIC", False),
            ("max_upload_size_mb", "Maximum upload size (MB)", "25", "NUMBER", "UPLOAD", False),
            ("session_timeout_minutes", "Session timeout (minutes)", "30", "NUMBER", "SECURITY", False),
            ("weekly_digest_enabled", "Weekly digest enabled", "true", "BOOLEAN", "NOTIFICATION", False),
            ("academic_terminology", "Academic terminology", '{"semester":"Semester","course":"Course","section":"Section"}', "JSON", "ACADEMIC", True),
        ]
        for key, label, value, value_type, group, is_public in rows:
            SystemSetting.objects.update_or_create(
                key=key,
                defaults={
                    "label": label,
                    "value": value,
                    "value_type": value_type,
                    "group": group,
                    "is_public": is_public,
                },
            )
        self.stdout.write("  System settings")

    def _notification_templates(self):
        templates = [
            (NotificationEvent.NEW_ASSIGNMENT, "New assignment in {{course_name}}", "Hello {{student_name}}, a new assignment has been posted."),
            (NotificationEvent.ASSIGNMENT_DEADLINE, "Deadline reminder", "Hello {{student_name}}, {{course_name}} work is due on {{deadline}}."),
            (NotificationEvent.MARKS_PUBLISHED, "Marks published", "Hello {{student_name}}, your marks are now available."),
            (NotificationEvent.ATTENDANCE_WARNING, "Attendance below the required level", "Hello {{student_name}}, your attendance needs attention."),
            (NotificationEvent.ANNOUNCEMENT, "{{title}}", "{{body}}"),
            (NotificationEvent.WEEKLY_DIGEST, "Your Weekly Public Health Academic Update", "{{body}}"),
        ]
        for event, subject, body in templates:
            NotificationTemplate.objects.update_or_create(
                event=event, defaults={"subject": subject, "body": body}
            )

    def _risk_rules(self):
        for index, rule in enumerate(DEFAULT_RISK_RULES):
            RiskRule.objects.update_or_create(
                code=rule["code"],
                defaults={
                    "label": rule["label"],
                    "metric": rule["metric"],
                    "operator": rule["operator"],
                    "threshold": Decimal(str(rule["threshold"])),
                    "weight": rule["weight"],
                    "guidance": rule["guidance"],
                    "display_order": index,
                },
            )

    def _department(self):
        department, _ = Department.objects.update_or_create(
            code="SPH",
            defaults={
                "name": "School of Public Health",
                "description": "Teaching and research in public health, epidemiology, biostatistics and health data science.",
                "email": "sph@srmist.demo",
                "established_year": 2016,
            },
        )
        Department.objects.update_or_create(
            code="EPI",
            defaults={
                "name": "Epidemiology",
                "description": "Population health and disease surveillance.",
                "established_year": 2019,
            },
        )
        self.stdout.write("  Departments")
        return department

    def _program(self, department):
        program, _ = Program.objects.update_or_create(
            code="MSC-HDS",
            defaults={
                "name": "M.Sc. Health Data Science",
                "department": department,
                "level": Program.Level.PG,
                "duration_years": 2,
                "total_semesters": 4,
                "total_credits": 80,
                "description": "A two-year postgraduate program combining public health, biostatistics and data science.",
            },
        )
        Program.objects.update_or_create(
            code="MPH",
            defaults={
                "name": "Master of Public Health",
                "department": department,
                "level": Program.Level.PG,
                "duration_years": 2,
                "total_semesters": 4,
                "total_credits": 76,
            },
        )
        return program

    def _sessions(self):
        session, _ = AcademicSession.objects.update_or_create(
            name="2026-27",
            defaults={
                "start_date": date(2026, 6, 1),
                "end_date": date(2027, 5, 31),
                "is_current": True,
            },
        )
        AcademicSession.objects.update_or_create(
            name="2025-26",
            defaults={
                "start_date": date(2025, 6, 1),
                "end_date": date(2026, 5, 31),
                "is_current": False,
            },
        )
        semesters = []
        for number, name, start, end, exam_start in [
            (1, "Semester 1 (Odd)", date(2026, 6, 15), date(2026, 11, 15), date(2026, 11, 20)),
            (2, "Semester 2 (Even)", date(2026, 12, 1), date(2027, 4, 30), date(2027, 5, 5)),
        ]:
            semester, _ = Semester.objects.update_or_create(
                session=session,
                number=number,
                defaults={
                    "name": name,
                    "start_date": start,
                    "end_date": end,
                    "exam_start_date": exam_start,
                    "exam_end_date": exam_start + timedelta(days=12),
                    "is_current": number == 1,
                },
            )
            semesters.append(semester)

        for name, day in [
            ("Independence Day", date(2026, 8, 15)),
            ("Gandhi Jayanti", date(2026, 10, 2)),
            ("Deepavali", date(2026, 11, 8)),
        ]:
            Holiday.objects.get_or_create(session=session, name=name, date=day)
        self.stdout.write("  Academic sessions and semesters")
        return session, semesters

    def _batch(self, program):
        batch, _ = Batch.objects.update_or_create(
            program=program,
            start_year=2026,
            name="M.Sc. HDS 2026-28",
            defaults={"end_year": 2028, "current_semester": 1},
        )
        return batch

    def _user(self, email, name, role, department, **extra):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": name,
                "role": role,
                "department": department,
                "is_active": True,
                "email_verified": True,
                **extra,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        return user

    def _staff(self, department):
        dean = self._user(
            "dean@sph.srmist.demo", "Dr. Vandana Krishnamurthy", Roles.DEAN, department
        )
        hod = self._user(
            "hod@sph.srmist.demo", "Dr. Prakash Venkataraman", Roles.ADMIN, department, is_staff=True
        )
        department.hod = hod
        department.save(update_fields=["hod"])

        faculty = []
        faculty_data = [
            ("faculty1@sph.srmist.demo", "Dr. Anitha Raghavan", "Epidemiology and disease modelling", FacultyProfile.Designation.PROFESSOR),
            ("faculty2@sph.srmist.demo", "Dr. Samuel Mathew", "Biostatistics and clinical trials", FacultyProfile.Designation.ASSOCIATE),
            ("faculty3@sph.srmist.demo", "Dr. Leena Chatterjee", "Health informatics and machine learning", FacultyProfile.Designation.ASSISTANT),
            ("faculty4@sph.srmist.demo", "Dr. Mohan Balasubramanian", "Environmental and occupational health", FacultyProfile.Designation.ASSISTANT),
        ]
        for index, (email, name, specialization, designation) in enumerate(faculty_data, start=1):
            user = self._user(email, name, Roles.FACULTY, department)
            FacultyProfile.objects.get_or_create(
                user=user,
                defaults={
                    "employee_id": "SPH-F%03d" % index,
                    "designation": designation,
                    "specialization": specialization,
                    "qualification": "Ph.D. Public Health",
                    "date_of_joining": date(2018 + index, 7, 1),
                    "office_location": "SPH Block, Room %s" % (200 + index),
                },
            )
            faculty.append(user)

        for user, employee_id, designation in [
            (dean, "SPH-D001", FacultyProfile.Designation.PROFESSOR),
            (hod, "SPH-A001", FacultyProfile.Designation.PROFESSOR),
        ]:
            FacultyProfile.objects.get_or_create(
                user=user,
                defaults={
                    "employee_id": employee_id,
                    "designation": designation,
                    "specialization": "Public health policy",
                    "qualification": "Ph.D.",
                    "date_of_joining": date(2016, 6, 1),
                },
            )
        self.stdout.write("  Dean, HOD and %s faculty" % len(faculty))
        return {"dean": dean, "hod": hod, "faculty": faculty}

    def _courses(self, department, program):
        for name, code, order in [
            ("Core", "CORE", 1), ("Elective", "ELECTIVE", 2), ("Practical", "PRACTICAL", 3),
            ("Seminar", "SEMINAR", 4), ("Research", "RESEARCH", 5), ("Internship", "INTERNSHIP", 6),
        ]:
            CourseType.objects.get_or_create(
                code=code, defaults={"name": name, "display_order": order}
            )
        core = CourseType.objects.get(code="CORE")
        practical = CourseType.objects.get(code="PRACTICAL")

        catalogue = [
            ("PHS5101", "Principles of Epidemiology", 4, 1, core, "Study design, measures of association, causal inference and outbreak investigation."),
            ("PHS5102", "Biostatistics for Public Health", 4, 1, core, "Descriptive statistics, probability, hypothesis testing and regression."),
            ("PHS5103", "Health Data Management", 3, 1, core, "Data models, EHR standards, data quality and governance."),
            ("PHS5104", "R and Python for Health Data", 3, 1, practical, "Applied programming for health datasets."),
            ("PHS5105", "Public Health Policy and Systems", 3, 1, core, "Health systems, financing and policy analysis."),
            ("PHS5201", "Machine Learning in Healthcare", 4, 2, core, "Supervised and unsupervised learning applied to clinical and population data."),
            ("PHS5202", "Survival and Longitudinal Analysis", 4, 2, core, "Time-to-event models and repeated measures."),
            ("PHS5203", "Geographic Information Systems in Health", 3, 2, practical, "Spatial epidemiology and disease mapping."),
        ]
        courses = []
        for code, name, credits, semester_number, course_type, description in catalogue:
            course, _ = Course.objects.update_or_create(
                code=code,
                department=department,
                defaults={
                    "name": name,
                    "credits": Decimal(str(credits)),
                    "program": program,
                    "semester_number": semester_number,
                    "course_type": course_type,
                    "description": description,
                    "status": Course.Status.ACTIVE,
                    "learning_outcomes": [
                        "Explain the core concepts of %s." % name.lower(),
                        "Apply appropriate methods to a public health dataset.",
                        "Communicate findings to a non-technical audience.",
                    ],
                    "syllabus": "Unit 1-5 covering the foundations and applications of %s." % name,
                },
            )
            courses.append(course)
        self.stdout.write("  %s courses" % len(courses))
        return courses

    def _sections(self, courses, semesters, batch, staff):
        sections = []
        faculty = staff["faculty"]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for index, course in enumerate(courses):
            semester = semesters[0] if course.semester_number == 1 else semesters[1]
            section, _ = CourseSection.objects.update_or_create(
                course=course,
                semester=semester,
                name="A",
                defaults={
                    "batch": batch,
                    "capacity": 60,
                    "room": "SPH-%s" % (101 + index),
                    "schedule": [
                        {
                            "day": days[index % len(days)],
                            "start_time": "09:00",
                            "end_time": "10:30",
                            "room": "SPH-%s" % (101 + index),
                        },
                        {
                            "day": days[(index + 2) % len(days)],
                            "start_time": "11:00",
                            "end_time": "12:30",
                            "room": "SPH-%s" % (101 + index),
                        },
                    ],
                },
            )
            instructor = faculty[index % len(faculty)]
            FacultyCourseAssignment.objects.get_or_create(
                section=section,
                faculty=instructor,
                defaults={"is_primary": True, "assignment_role": "INSTRUCTOR"},
            )
            course.coordinator = instructor
            course.save(update_fields=["coordinator"])
            sections.append(section)
        self.stdout.write("  %s course sections" % len(sections))
        return sections

    def _curriculum(self, program, batch, courses):
        for index, course in enumerate(courses):
            CurriculumItem.objects.update_or_create(
                program=program,
                batch=batch,
                semester_number=course.semester_number,
                course=course,
                defaults={
                    "credits": course.credits,
                    "category": (
                        CurriculumItem.Category.PRACTICAL
                        if course.course_type and course.course_type.code == "PRACTICAL"
                        else CurriculumItem.Category.CORE
                    ),
                    "display_order": index,
                },
            )

    def _students(self, department, program, batch, count):
        students = []
        for index in range(1, count + 1):
            name = "%s %s" % (
                FIRST_NAMES[(index - 1) % len(FIRST_NAMES)],
                LAST_NAMES[(index * 3) % len(LAST_NAMES)],
            )
            user = self._user(
                "student%d@sph.srmist.demo" % index, name, Roles.STUDENT, department
            )
            StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "enrollment_number": "RA26HDS%03d" % index,
                    "program": program,
                    "batch": batch,
                    "current_semester": 1,
                    "admission_date": date(2026, 6, 15),
                    "guardian_name": "%s %s" % (
                        FIRST_NAMES[(index * 5) % len(FIRST_NAMES)],
                        LAST_NAMES[(index * 3) % len(LAST_NAMES)],
                    ),
                    "guardian_phone": "+91 90000%05d" % index,
                    "address": "Kattankulathur, Chengalpattu District, Tamil Nadu",
                },
            )
            students.append(user)
        self.stdout.write("  %s students" % len(students))
        return students

    def _scholars(self, department, staff):
        scholars = []
        data = [
            ("scholar1@sph.srmist.demo", "Nithya Raman", "Spatial epidemiology of vector-borne disease"),
            ("scholar2@sph.srmist.demo", "Abhishek Deshpande", "Machine learning for early sepsis detection"),
            ("scholar3@sph.srmist.demo", "Fatima Sheikh", "Maternal health outcomes in rural cohorts"),
        ]
        for index, (email, name, area) in enumerate(data, start=1):
            user = self._user(email, name, Roles.SCHOLAR, department)
            ScholarProfile.objects.get_or_create(
                user=user,
                defaults={
                    "registration_number": "SPH-RS%03d" % index,
                    "research_area": area,
                    "supervisor": staff["faculty"][index % len(staff["faculty"])],
                    "enrolment_year": 2024 + (index % 2),
                    "is_teaching_assistant": index == 1,
                    "thesis_title": area,
                },
            )
            scholars.append(user)
        self.stdout.write("  %s research scholars" % len(scholars))
        return scholars

    def _alumni(self, department, program):
        alumni = []
        data = [
            ("alumni1@sph.srmist.demo", "Deepa Subramanian", 2024, "Apollo Hospitals", "Health Data Analyst", "Chennai", ["SQL", "Python", "Epidemiology"], True),
            ("alumni2@sph.srmist.demo", "Ravi Shankar", 2023, "World Health Organization", "Surveillance Officer", "New Delhi", ["R", "Surveillance", "GIS"], True),
            ("alumni3@sph.srmist.demo", "Elizabeth John", 2024, "Novartis", "Biostatistician", "Hyderabad", ["SAS", "Clinical trials"], False),
            ("alumni4@sph.srmist.demo", "Gaurav Malhotra", 2022, "PATH India", "Program Manager", "Bengaluru", ["Program design", "M&E"], True),
        ]
        for email, name, year, org, title, location, skills, mentoring in data:
            user = self._user(email, name, Roles.ALUMNI, department)
            AlumniProfile.objects.get_or_create(
                user=user,
                defaults={
                    "graduation_year": year,
                    "program": program,
                    "current_organization": org,
                    "job_title": title,
                    "location": location,
                    "skills": skills,
                    "is_available_for_mentorship": mentoring,
                    "mentorship_areas": skills[:2],
                    "show_in_directory": True,
                },
            )
            alumni.append(user)
        self.stdout.write("  %s alumni" % len(alumni))
        return alumni

    def _enrol(self, students, sections):
        semester_one = [section for section in sections if section.course.semester_number == 1]
        count = 0
        for student in students:
            for section in semester_one:
                _, created = Enrollment.objects.get_or_create(
                    student=student, section=section, defaults={"status": Enrollment.Status.ACTIVE}
                )
                count += int(created)
        self.stdout.write("  %s enrolments" % count)

    def _grade_scale(self, department):
        scale, _ = GradeScale.objects.update_or_create(
            name="SRMIST Postgraduate Scale",
            defaults={
                "description": "Ten-point grading scale used for postgraduate programs.",
                "is_default": True,
            },
        )
        bands = [
            ("O", 91, 100, 10, "Outstanding", True),
            ("A+", 81, 90, 9, "Excellent", True),
            ("A", 71, 80, 8, "Very good", True),
            ("B+", 61, 70, 7, "Good", True),
            ("B", 56, 60, 6, "Above average", True),
            ("C", 50, 55, 5, "Average", True),
            ("P", 40, 49, 4, "Pass", True),
            ("F", 0, 39, 0, "Fail", False),
        ]
        for letter, low, high, point, description, is_pass in bands:
            GradeBand.objects.update_or_create(
                scale=scale,
                letter=letter,
                defaults={
                    "min_percentage": Decimal(str(low)),
                    "max_percentage": Decimal(str(high)),
                    "grade_point": Decimal(str(point)),
                    "description": description,
                    "is_pass": is_pass,
                },
            )
        self.stdout.write("  Grading scale")

    def _attendance_policy(self, department):
        AttendancePolicy.objects.update_or_create(
            department=None,
            name="Institution default",
            defaults={
                "warning_threshold": Decimal("75"),
                "critical_threshold": Decimal("65"),
                "consecutive_absence_alert": 3,
            },
        )
        AttendancePolicy.objects.update_or_create(
            department=department,
            name="School of Public Health policy",
            defaults={
                "warning_threshold": Decimal("75"),
                "critical_threshold": Decimal("65"),
                "consecutive_absence_alert": 3,
            },
        )

    def _attendance(self, sections, students):
        semester_one = [section for section in sections if section.course.semester_number == 1]
        today = timezone.localdate()
        created_sessions = 0
        created_records = 0

        # Give each student a stable attendance "profile" so the analytics tell a story.
        profiles = {}
        for index, student in enumerate(students):
            if index % 12 == 0:
                profiles[student.id] = 0.58   # struggling
            elif index % 7 == 0:
                profiles[student.id] = 0.71   # borderline
            elif index % 5 == 0:
                profiles[student.id] = 0.82
            else:
                profiles[student.id] = 0.93

        for section in semester_one:
            for week in range(10, 0, -1):
                session_date = today - timedelta(days=week * 7 - (hash(str(section.id)) % 5))
                if session_date > today:
                    continue
                session, created = AttendanceSession.objects.get_or_create(
                    section=section,
                    date=session_date,
                    period=1,
                    defaults={
                        "topic": "Week %s session" % (11 - week),
                        "status": AttendanceSession.Status.FINALIZED,
                        "finalized_at": timezone.now(),
                    },
                )
                created_sessions += int(created)
                if not created:
                    continue
                for student in students:
                    if not Enrollment.objects.filter(
                        student=student, section=section, status=Enrollment.Status.ACTIVE
                    ).exists():
                        continue
                    roll = random.random()
                    rate = profiles[student.id]
                    if roll < rate:
                        status_value = AttendanceRecord.Status.PRESENT
                    elif roll < rate + 0.06:
                        status_value = AttendanceRecord.Status.LATE
                    elif roll < rate + 0.09:
                        status_value = AttendanceRecord.Status.EXCUSED
                    else:
                        status_value = AttendanceRecord.Status.ABSENT
                    AttendanceRecord.objects.get_or_create(
                        session=session, student=student, defaults={"status": status_value}
                    )
                    created_records += 1
        self.stdout.write("  %s attendance sessions, %s records" % (created_sessions, created_records))

    def _assessments(self, sections, students):
        semester_one = [section for section in sections if section.course.semester_number == 1]
        components_spec = [
            ("Assignment", AssessmentComponent.Kind.ASSIGNMENT, 20, 10),
            ("Quiz", AssessmentComponent.Kind.QUIZ, 20, 10),
            ("Mid-term examination", AssessmentComponent.Kind.MIDTERM, 50, 20),
            ("Seminar", AssessmentComponent.Kind.SEMINAR, 20, 10),
        ]
        count = 0
        for section in semester_one:
            for order, (name, kind, max_marks, weight) in enumerate(components_spec):
                component, _ = AssessmentComponent.objects.update_or_create(
                    section=section,
                    name=name,
                    defaults={
                        "kind": kind,
                        "max_marks": Decimal(str(max_marks)),
                        "weight": Decimal(str(weight)),
                        "display_order": order,
                    },
                )
                for index, student in enumerate(students):
                    if not Enrollment.objects.filter(
                        student=student, section=section, status=Enrollment.Status.ACTIVE
                    ).exists():
                        continue
                    base = 0.55 if index % 12 == 0 else (0.68 if index % 7 == 0 else 0.82)
                    value = min(max(random.gauss(base, 0.12), 0.15), 1.0)
                    ComponentScore.objects.update_or_create(
                        component=component,
                        student=student,
                        defaults={
                            "marks_obtained": round(Decimal(str(value)) * component.max_marks, 2),
                            "status": ComponentScore.Status.PUBLISHED,
                            "published_at": timezone.now(),
                        },
                    )
                    count += 1

            for index, student in enumerate(students[:20]):
                if not Enrollment.objects.filter(
                    student=student, section=section, status=Enrollment.Status.ACTIVE
                ).exists():
                    continue
                base = 0.55 if index % 12 == 0 else 0.78
                ExternalMark.objects.update_or_create(
                    student=student,
                    section=section,
                    kind=ExternalMark.Kind.THEORY,
                    defaults={
                        "marks_obtained": round(
                            Decimal(str(min(max(random.gauss(base, 0.1), 0.2), 1.0))) * 60, 2
                        ),
                        "max_marks": Decimal("60"),
                        "status": ExternalMark.Status.PUBLISHED,
                    },
                )
        self.stdout.write("  %s component scores" % count)

    def _assignments(self, sections, students, staff):
        semester_one = [section for section in sections if section.course.semester_number == 1]
        now = timezone.now()
        created = 0
        for index, section in enumerate(semester_one):
            component = AssessmentComponent.objects.filter(
                section=section, kind=AssessmentComponent.Kind.ASSIGNMENT
            ).first()
            specs = [
                ("Assignment 1: Literature critique", now - timedelta(days=12), Assignment.Status.CLOSED),
                ("Assignment 2: Applied data exercise", now + timedelta(days=6), Assignment.Status.PUBLISHED),
            ]
            for title, due, status_value in specs:
                assignment, was_created = Assignment.objects.update_or_create(
                    section=section,
                    title="%s (%s)" % (title, section.course.code),
                    defaults={
                        "description": "Work through the brief and submit a written response with your analysis.",
                        "instructions": "Submit a single PDF. Cite all sources. Late work is accepted with a penalty.",
                        "max_marks": Decimal("20"),
                        "due_date": due,
                        "status": status_value,
                        "published_at": now - timedelta(days=20),
                        "allow_late_submission": True,
                        "late_penalty_percent": Decimal("10"),
                        "allowed_extensions": ["pdf", "docx"],
                        "component": component,
                    },
                )
                created += int(was_created)

                if status_value == Assignment.Status.CLOSED:
                    for student_index, student in enumerate(students):
                        if not Enrollment.objects.filter(
                            student=student, section=section, status=Enrollment.Status.ACTIVE
                        ).exists():
                            continue
                        # A realistic slice of students miss the deadline entirely.
                        if student_index % 11 == 0:
                            continue
                        late = student_index % 9 == 0
                        marks = Decimal(str(round(random.uniform(11, 19), 2)))
                        AssignmentSubmission.objects.update_or_create(
                            assignment=assignment,
                            student=student,
                            defaults={
                                "text_response": "Submitted analysis for %s." % section.course.code,
                                "submitted_at": due + timedelta(hours=6) if late else due - timedelta(days=1),
                                "status": AssignmentSubmission.Status.GRADED,
                                "marks_obtained": marks,
                                "feedback": "Clear structure. Strengthen the discussion of limitations.",
                                "graded_at": now - timedelta(days=5),
                                "graded_by": staff["faculty"][index % len(staff["faculty"])],
                            },
                        )
        self.stdout.write("  %s assignments" % created)

    def _notes(self, courses, sections, staff):
        count = 0
        for index, course in enumerate(courses):
            section = next((s for s in sections if s.course_id == course.id), None)
            topics = [
                ("Unit 1 - Foundations", "Introductory concepts and terminology."),
                ("Unit 2 - Methods", "Core analytical methods with worked examples."),
                ("Unit 3 - Applications", "Case studies drawn from public health practice."),
            ]
            for topic_index, (topic, description) in enumerate(topics):
                note, created = Note.objects.get_or_create(
                    title="%s - %s" % (course.code, topic),
                    course=course,
                    defaults={
                        "description": description,
                        "section": section,
                        "department": course.department,
                        "semester_number": course.semester_number,
                        "topic": topic,
                        "tags": [course.code.lower(), "lecture", "unit%s" % (topic_index + 1)],
                        "visibility": Note.Visibility.COURSE,
                        "created_by": staff["faculty"][index % len(staff["faculty"])],
                    },
                )
                if created:
                    NoteVersion.objects.create(
                        note=note,
                        version_number=1,
                        file="notes/demo/%s-unit%s.pdf" % (course.code.lower(), topic_index + 1),
                        original_filename="%s-unit%s.pdf" % (course.code.lower(), topic_index + 1),
                        file_size=random.randint(180_000, 3_400_000),
                        content_type="application/pdf",
                        changelog="Initial upload",
                    )
                    count += 1
        self.stdout.write("  %s notes" % count)

    def _question_bank(self, courses, staff):
        count = 0
        for index, course in enumerate(courses[:5]):
            parent, _ = QuestionTopic.objects.get_or_create(
                course=course, name="Core concepts", parent=None
            )
            child, _ = QuestionTopic.objects.get_or_create(
                course=course, name="Applied methods", parent=parent
            )
            samples = [
                (
                    "Which measure of association is most appropriate for a case-control study?",
                    Question.QuestionType.MCQ,
                    Question.Difficulty.MEDIUM,
                    [("Odds ratio", True), ("Risk ratio", False), ("Hazard ratio", False), ("Attributable risk", False)],
                    "Case-control studies sample on outcome, so the odds ratio is the estimable measure.",
                ),
                (
                    "A p-value below 0.05 proves that the alternative hypothesis is true.",
                    Question.QuestionType.TRUE_FALSE,
                    Question.Difficulty.EASY,
                    [("True", False), ("False", True)],
                    "A p-value quantifies evidence against the null hypothesis; it proves nothing.",
                ),
                (
                    "Explain how confounding differs from effect modification, with an example from public health practice.",
                    Question.QuestionType.LONG,
                    Question.Difficulty.HARD,
                    [],
                    "Confounding distorts an association; effect modification means the effect genuinely differs across strata.",
                ),
                (
                    "Calculate the incidence rate given 24 new cases over 1,200 person-years of follow-up.",
                    Question.QuestionType.NUMERICAL,
                    Question.Difficulty.MEDIUM,
                    [],
                    "24 / 1200 = 0.02 cases per person-year, or 20 per 1,000 person-years.",
                ),
            ]
            for text, question_type, difficulty, options, explanation in samples:
                question, created = Question.objects.get_or_create(
                    course=course,
                    text=text,
                    defaults={
                        "topic": child if question_type == Question.QuestionType.LONG else parent,
                        "question_type": question_type,
                        "difficulty": difficulty,
                        "marks": Decimal("2") if options else Decimal("10"),
                        "explanation": explanation,
                        "correct_answer": "" if options else explanation,
                        "status": Question.Status.APPROVED,
                        "tags": [course.code.lower()],
                        "created_by": staff["faculty"][index % len(staff["faculty"])],
                    },
                )
                if created:
                    for order, (option_text, is_correct) in enumerate(options):
                        QuestionOption.objects.create(
                            question=question,
                            text=option_text,
                            is_correct=is_correct,
                            display_order=order,
                        )
                    count += 1
        self.stdout.write("  %s questions" % count)

    def _announcements(self, department, staff, courses):
        for name, color, order in [
            ("Academic", "blue", 1), ("Examination", "amber", 2),
            ("Event", "emerald", 3), ("Administrative", "slate", 4),
        ]:
            AnnouncementCategory.objects.get_or_create(
                name=name, defaults={"color": color, "display_order": order}
            )
        academic = AnnouncementCategory.objects.get(name="Academic")
        exam = AnnouncementCategory.objects.get(name="Examination")
        now = timezone.now()

        rows = [
            ("Semester 1 mid-term timetable published", "The mid-term examination timetable for Semester 1 is now available. Examinations begin on 20 November 2026 in the SPH block.", Announcement.Priority.IMPORTANT, exam, True),
            ("Guest lecture: Outbreak analytics in practice", "Dr. Meera Sundaram from the National Institute of Epidemiology will speak on real-time outbreak analytics this Friday at 3 pm.", Announcement.Priority.NORMAL, academic, False),
            ("Attendance review for Semester 1", "Students below the 75% attendance requirement will be contacted by their course coordinators this week.", Announcement.Priority.URGENT, academic, True),
            ("Library access to Lancet Global Health renewed", "Institutional access has been renewed for the 2026-27 session. Use the e-resources page for the direct link.", Announcement.Priority.NORMAL, None, False),
        ]
        for title, body, priority, category, pinned in rows:
            Announcement.objects.get_or_create(
                title=title,
                defaults={
                    "body": body,
                    "priority": priority,
                    "category": category,
                    "audience": Announcement.Audience.DEPARTMENT,
                    "department": department,
                    "status": Announcement.Status.PUBLISHED,
                    "publish_at": now - timedelta(days=random.randint(1, 10)),
                    "expires_at": now + timedelta(days=30),
                    "is_pinned": pinned,
                    "created_by": staff["hod"],
                },
            )
        self.stdout.write("  Announcements")

    def _calendar(self, department, session):
        now = timezone.now()
        rows = [
            ("Mid-term examinations begin", "EXAMINATION", 18, "SPH Examination Hall"),
            ("Research seminar: spatial epidemiology", "SEMINAR", 5, "SPH Seminar Room"),
            ("World Health Day symposium", "EVENT", 12, "Main Auditorium"),
            ("Faculty-student mentoring meeting", "MEETING", 3, "SPH Block, Room 204"),
            ("Dissertation proposal presentations", "RESEARCH", 25, "SPH Seminar Room"),
        ]
        for title, category, days_ahead, location in rows:
            CalendarEvent.objects.get_or_create(
                title=title,
                defaults={
                    "description": "%s organised by the School of Public Health." % title,
                    "category": category,
                    "start_at": now + timedelta(days=days_ahead, hours=3),
                    "end_at": now + timedelta(days=days_ahead, hours=5),
                    "location": location,
                    "audience": CalendarEvent.Audience.DEPARTMENT,
                    "department": department,
                },
            )
        self.stdout.write("  Calendar events")

    def _forums(self, sections, students, staff):
        section = sections[0]
        thread, created = DiscussionThread.objects.get_or_create(
            section=section,
            title="Clarification on confounding versus effect modification",
            defaults={
                "author": students[0],
                "body": "In the Unit 2 example, why is age treated as a confounder rather than an effect modifier? Both seem to change the estimate.",
                "tags": ["epidemiology", "unit2"],
                "status": DiscussionThread.Status.ANSWERED,
            },
        )
        if created:
            reply = DiscussionReply.objects.create(
                thread=thread,
                author=staff["faculty"][0],
                body=(
                    "Good question. Age is a confounder there because it is associated with both the "
                    "exposure and the outcome and is not on the causal pathway. It would be an effect "
                    "modifier only if the strength of the exposure-outcome association genuinely "
                    "differed across age strata - check the stratum-specific estimates."
                ),
                is_accepted_answer=True,
                helpful_count=6,
            )
            DiscussionReply.objects.create(
                thread=thread,
                author=students[1],
                parent=reply,
                body="That helps, thank you. So the stratified estimates being similar is the giveaway.",
                helpful_count=2,
            )
            thread.reply_count = 2
            thread.view_count = 34
            thread.save(update_fields=["reply_count", "view_count"])

        DiscussionThread.objects.get_or_create(
            section=sections[1],
            title="Which R package should we use for the survival analysis exercise?",
            defaults={
                "author": students[2],
                "body": "The brief mentions Kaplan-Meier curves. Should we use survival and survminer, or is base R acceptable?",
                "tags": ["r", "practical"],
            },
        )
        self.stdout.write("  Discussion threads")

    def _research(self, department, scholars, staff):
        projects = [
            ("Spatial clustering of dengue incidence in peri-urban Chennai", scholars[0], "ONGOING", "Indian Council of Medical Research", 1850000),
            ("Early warning models for sepsis in tertiary care", scholars[1], "ONGOING", "Department of Biotechnology", 2400000),
            ("Maternal health outcomes in rural Tamil Nadu: a cohort study", scholars[2], "PROPOSED", "", None),
        ]
        for title, owner, status_value, funder, amount in projects:
            project, created = ResearchProject.objects.get_or_create(
                title=title,
                defaults={
                    "abstract": "A study examining %s using routinely collected health data." % title.lower(),
                    "principal_investigator": owner,
                    "department": department,
                    "research_area": getattr(owner.scholar_profile, "research_area", ""),
                    "funding_agency": funder,
                    "funding_amount": Decimal(str(amount)) if amount else None,
                    "start_date": date(2025, 8, 1),
                    "expected_end_date": date(2027, 7, 31),
                    "status": status_value,
                    "ethics_approval_reference": "IEC/2025/%s" % random.randint(100, 999),
                    "dataset_references": ["National Family Health Survey", "District health records"],
                },
            )
            if created:
                for order, (milestone, milestone_status) in enumerate(
                    [
                        ("Literature review", ResearchMilestone.Status.COMPLETED),
                        ("Ethics approval", ResearchMilestone.Status.COMPLETED),
                        ("Data collection", ResearchMilestone.Status.IN_PROGRESS),
                        ("Analysis and writing", ResearchMilestone.Status.PENDING),
                    ]
                ):
                    ResearchMilestone.objects.create(
                        project=project,
                        title=milestone,
                        status=milestone_status,
                        due_date=date(2026, 3 + order * 2, 1),
                        display_order=order,
                    )

        publications = [
            ("Spatiotemporal patterns of dengue transmission in a South Indian city", scholars[0], "PLOS Neglected Tropical Diseases", 2025, "10.1371/journal.pntd.demo1"),
            ("A gradient boosting approach to early sepsis detection", scholars[1], "Journal of Biomedical Informatics", 2026, "10.1016/j.jbi.demo2"),
            ("Health system readiness for climate-sensitive disease", staff["faculty"][0], "Lancet Regional Health - Southeast Asia", 2025, "10.1016/j.lansea.demo3"),
        ]
        for title, owner, venue, year, doi in publications:
            Publication.objects.get_or_create(
                title=title,
                defaults={
                    "authors": "%s; %s" % (owner.full_name, staff["faculty"][0].full_name),
                    "owner": owner,
                    "venue": venue,
                    "year": year,
                    "doi": doi,
                    "publication_type": Publication.PublicationType.JOURNAL,
                    "status": Publication.Status.PUBLISHED,
                    "citation_count": random.randint(0, 24),
                    "abstract": "This study investigates %s." % title.lower(),
                },
            )
        self.stdout.write("  Research projects and publications")

    def _alumni_content(self, alumni, students):
        rows = [
            ("Health Data Analyst", "Apollo Hospitals", JobPosting.OpportunityType.JOB, "Chennai", JobPosting.WorkMode.ONSITE, "M.Sc. in health data science, biostatistics or a related field.", 45),
            ("Epidemiology Intern", "National Institute of Epidemiology", JobPosting.OpportunityType.INTERNSHIP, "Chennai", JobPosting.WorkMode.HYBRID, "Currently enrolled postgraduate students.", 20),
            ("Research Assistant - Global Health", "PATH India", JobPosting.OpportunityType.RESEARCH, "Bengaluru", JobPosting.WorkMode.HYBRID, "Postgraduate degree with quantitative training.", 30),
            ("WHO Public Health Fellowship 2027", "World Health Organization", JobPosting.OpportunityType.FELLOWSHIP, "New Delhi", JobPosting.WorkMode.ONSITE, "Graduates within two years of completion.", 60),
        ]
        for title, org, opportunity_type, location, mode, eligibility, days in rows:
            JobPosting.objects.get_or_create(
                title=title,
                organization=org,
                defaults={
                    "opportunity_type": opportunity_type,
                    "work_mode": mode,
                    "location": location,
                    "description": "%s at %s. Work alongside a multidisciplinary public health team on live data." % (title, org),
                    "eligibility": eligibility,
                    "skills_required": ["Python", "Statistics", "Communication"],
                    "stipend_or_salary": "As per organisation norms",
                    "contact_email": "careers@%s.demo" % org.split()[0].lower(),
                    "deadline": timezone.localdate() + timedelta(days=days),
                    "posted_by": alumni[0],
                    "status": JobPosting.Status.PUBLISHED,
                },
            )
        MentorshipRequest.objects.get_or_create(
            requester=students[0],
            mentor=alumni[0],
            topic="Moving into health data analytics after the M.Sc.",
            defaults={
                "message": "I would value 30 minutes to discuss which technical skills matter most in a hospital analytics team.",
                "status": MentorshipRequest.Status.PENDING,
            },
        )
        self.stdout.write("  Jobs and mentorship")

    def _library(self, department):
        categories = [
            ("Journals", "Peer-reviewed public health journals", 1),
            ("Databases", "Bibliographic and statistical databases", 2),
            ("Government portals", "Official health statistics and policy", 3),
            ("Learning platforms", "Courses and tutorials", 4),
        ]
        for name, description, order in categories:
            ResourceCategory.objects.get_or_create(
                name=name, defaults={"description": description, "display_order": order}
            )

        rows = [
            ("PubMed", "Biomedical literature database maintained by the NIH.", "Databases", "https://pubmed.ncbi.nlm.nih.gov/", "OPEN"),
            ("WHO Global Health Observatory", "Health statistics for WHO member states.", "Government portals", "https://www.who.int/data/gho", "OPEN"),
            ("The Lancet Global Health", "Open-access global health journal.", "Journals", "https://www.thelancet.com/journals/langlo", "OPEN"),
            ("National Family Health Survey (India)", "Nationally representative household survey data.", "Government portals", "https://rchiips.org/nfhs/", "OPEN"),
            ("Cochrane Library", "Systematic reviews of health interventions.", "Databases", "https://www.cochranelibrary.com/", "INSTITUTIONAL"),
            ("R for Data Science", "Free textbook on the tidyverse workflow.", "Learning platforms", "https://r4ds.hadley.nz/", "OPEN"),
        ]
        for title, description, category_name, url, access in rows:
            ResourceLink.objects.get_or_create(
                title=title,
                defaults={
                    "description": description,
                    "category": ResourceCategory.objects.filter(name=category_name).first(),
                    "url": url,
                    "access_type": access,
                    "department": department,
                    "tags": ["public health"],
                },
            )
        self.stdout.write("  E-resources")

    def _feedback(self, department, sections):
        form, created = FeedbackForm.objects.get_or_create(
            title="Semester 1 course feedback",
            defaults={
                "description": "Your responses are anonymous and help improve teaching in the School of Public Health.",
                "form_type": FeedbackForm.FormType.COURSE,
                "is_anonymous": True,
                "department": department,
                "target_roles": [Roles.STUDENT],
                "status": FeedbackForm.Status.OPEN,
                "closes_at": timezone.now() + timedelta(days=21),
            },
        )
        if created:
            questions = [
                ("The learning outcomes were communicated clearly.", FeedbackQuestion.QuestionType.RATING, []),
                ("Course materials were available in good time.", FeedbackQuestion.QuestionType.RATING, []),
                ("The pace of teaching was appropriate.", FeedbackQuestion.QuestionType.RATING, []),
                ("Which aspect of the course was most useful?", FeedbackQuestion.QuestionType.CHOICE, ["Lectures", "Practicals", "Assignments", "Discussions"]),
                ("What one change would improve this course?", FeedbackQuestion.QuestionType.TEXT, []),
            ]
            for order, (text, question_type, choices) in enumerate(questions):
                FeedbackQuestion.objects.create(
                    form=form,
                    text=text,
                    question_type=question_type,
                    choices=choices,
                    display_order=order,
                    is_required=question_type != FeedbackQuestion.QuestionType.TEXT,
                )
        self.stdout.write("  Feedback form")

    def _certificates(self, department, students, staff):
        for index, student in enumerate(students[:6]):
            Certificate.objects.get_or_create(
                holder=student,
                title="Workshop on Reproducible Research in R",
                defaults={
                    "description": "Two-day workshop covering literate programming and version control.",
                    "certificate_type": Certificate.CertificateType.WORKSHOP,
                    "issued_on": timezone.localdate() - timedelta(days=30 + index),
                    "issuing_department": department,
                    "issued_by": staff["hod"],
                },
            )
        self.stdout.write("  Certificates")

    def _widgets(self):
        layout = {
            Roles.STUDENT: [
                ("kpi_summary", "Key figures", 3), ("attendance_chart", "Attendance trend", 2),
                ("upcoming_assignments", "Upcoming assignments", 1), ("recent_marks", "Recent marks", 1),
                ("announcements", "Announcements", 1), ("calendar", "Calendar", 1),
                ("risk_indicator", "Academic support", 1),
            ],
            Roles.FACULTY: [
                ("kpi_summary", "Key figures", 3), ("todays_classes", "Today's classes", 1),
                ("pending_grading", "Pending grading", 1), ("section_performance", "Section performance", 2),
                ("at_risk", "Students needing support", 2),
            ],
            Roles.ADMIN: [
                ("kpi_summary", "Key figures", 3), ("course_performance", "Course performance", 2),
                ("faculty_workload", "Faculty workload", 1), ("at_risk", "Students needing support", 2),
            ],
            Roles.DEAN: [
                ("kpi_summary", "Key figures", 3), ("department_comparison", "Department comparison", 2),
                ("risk_distribution", "Risk distribution", 1), ("attendance_overview", "Attendance overview", 2),
            ],
            Roles.SCHOLAR: [
                ("kpi_summary", "Key figures", 3), ("research_summary", "Research", 2),
                ("todays_classes", "Teaching", 1),
            ],
            Roles.ALUMNI: [
                ("kpi_summary", "Key figures", 3), ("mentorship_requests", "Mentorship requests", 2),
                ("jobs", "Opportunities", 1),
            ],
        }
        for role, widgets in layout.items():
            for order, (key, label, span) in enumerate(widgets):
                DashboardWidget.objects.update_or_create(
                    widget_key=key,
                    role=role,
                    defaults={"label": label, "display_order": order, "column_span": span},
                )

    def _activity(self, students):
        now = timezone.now()
        for index, student in enumerate(students):
            # A few students look inactive so the risk indicator has something to find.
            days_back = 25 if index % 12 == 0 else random.randint(0, 5)
            log = ActivityLog.objects.create(user=student, action="dashboard.view")
            # created_at is auto_now_add, so backdate it explicitly.
            ActivityLog.objects.filter(pk=log.pk).update(
                created_at=now - timedelta(days=days_back)
            )
            User.objects.filter(pk=student.pk).update(last_active_at=now - timedelta(days=days_back))
