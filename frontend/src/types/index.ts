export type Role = 'DEAN' | 'ADMIN' | 'FACULTY' | 'SCHOLAR' | 'STUDENT' | 'ALUMNI';

export interface StudentProfile {
  id: string;
  enrollment_number: string;
  program?: string | null;
  program_name?: string;
  batch?: string | null;
  batch_name?: string;
  current_semester: number;
  admission_date?: string | null;
  guardian_name?: string;
  guardian_phone?: string;
  address?: string;
}

export interface FacultyProfile {
  id: string;
  employee_id: string;
  designation: string;
  designation_display: string;
  specialization: string;
  qualification: string;
  date_of_joining?: string | null;
  office_location?: string;
}

export interface ScholarProfile {
  id: string;
  registration_number: string;
  research_area: string;
  supervisor?: string | null;
  supervisor_name?: string;
  scholar_type: string;
  enrolment_year?: number | null;
  is_teaching_assistant: boolean;
  thesis_title?: string;
}

export interface AlumniProfile {
  id: string;
  graduation_year: number;
  program?: string | null;
  program_name?: string;
  current_organization: string;
  job_title: string;
  location: string;
  skills: string[];
  linkedin_url?: string;
  website_url?: string;
  is_available_for_mentorship: boolean;
  mentorship_areas: string[];
  show_email: boolean;
  show_phone: boolean;
  show_in_directory: boolean;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  avatar?: string | null;
  role: Role;
  role_display: string;
  department?: string | null;
  department_name?: string;
  department_code?: string;
  bio?: string;
  is_active: boolean;
  email_verified: boolean;
  must_change_password: boolean;
  theme_preference: 'light' | 'dark' | 'system';
  locale: string;
  timezone_name: string;
  date_joined: string;
  last_active_at?: string | null;
  initials: string;
  permissions: string[];
  profile?: StudentProfile | FacultyProfile | ScholarProfile | AlumniProfile | null;
}

export interface UserBrief {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  role_display: string;
  avatar?: string | null;
  initials: string;
}

export interface Department {
  id: string;
  name: string;
  code: string;
  description: string;
  hod?: string | null;
  hod_name?: string;
  email: string;
  phone: string;
  established_year?: number | null;
  is_active: boolean;
  program_count: number;
  member_count: number;
}

export interface Course {
  id: string;
  code: string;
  name: string;
  description: string;
  credits: string;
  department: string;
  department_name: string;
  department_code: string;
  program?: string | null;
  program_name?: string;
  semester_number: number;
  course_type?: string | null;
  course_type_name?: string;
  coordinator?: string | null;
  coordinator_detail?: UserBrief | null;
  syllabus: string;
  learning_outcomes: string[];
  status: 'DRAFT' | 'ACTIVE' | 'ARCHIVED';
  section_count: number;
}

export interface CourseSection {
  id: string;
  course: string;
  course_code: string;
  course_name: string;
  course_credits: string;
  semester: string;
  semester_name: string;
  session_name: string;
  batch?: string | null;
  batch_name?: string;
  department_id: string;
  name: string;
  capacity: number;
  room: string;
  schedule: { day: string; start_time: string; end_time: string; room?: string }[];
  is_active: boolean;
  faculty: { id: string; full_name: string; role: string; is_primary: boolean }[];
  enrolled_count: number;
}

export interface AttendanceSummary {
  present: number;
  absent: number;
  late: number;
  excused: number;
  total: number;
  percentage: number;
  status: 'ok' | 'warning' | 'critical';
  warning_threshold: number;
  critical_threshold: number;
  sessions_to_reach_threshold: number;
}

export interface CourseAttendance extends AttendanceSummary {
  section_id: string;
  section_name: string;
  course_code: string;
  course_name: string;
}

export interface RiskFactor {
  code: string;
  label: string;
  weight: number;
  metric: string;
  observed: number;
  threshold: number;
  guidance: string;
}

export interface RiskOutcome {
  score: number;
  level: 'low' | 'moderate' | 'high' | 'critical';
  level_label: string;
  factors: RiskFactor[];
  indicator_name: string;
  disclaimer: string;
  metrics?: Record<string, number | null>;
  student?: { id: string; full_name: string; enrollment_number: string };
}

export interface Assignment {
  id: string;
  section: string;
  course_code: string;
  course_name: string;
  section_name: string;
  title: string;
  description: string;
  instructions: string;
  attachment?: string | null;
  max_marks: string;
  due_date: string;
  allow_late_submission: boolean;
  late_penalty_percent: string;
  allowed_extensions: string[];
  max_file_size_mb: number;
  allow_resubmission: boolean;
  status: 'DRAFT' | 'PUBLISHED' | 'CLOSED';
  is_open: boolean;
  submission_stats?: {
    enrolled: number;
    submitted: number;
    pending: number;
    graded: number;
    late: number;
  } | null;
  my_submission?: {
    id: string;
    status: string;
    submitted_at: string;
    marks_obtained: number | null;
    feedback: string;
    file: string | null;
    is_late: boolean;
  } | null;
  created_at: string;
}

export interface Note {
  id: string;
  title: string;
  description: string;
  course: string;
  course_code: string;
  course_name: string;
  section?: string | null;
  department: string;
  department_name: string;
  semester_number: number;
  topic: string;
  tags: string[];
  visibility: string;
  allow_download: boolean;
  is_published: boolean;
  download_count: number;
  view_count: number;
  uploaded_by: string;
  version_count: number;
  created_at: string;
  active_version_detail?: {
    id: string;
    version_number: number;
    file: string;
    original_filename: string;
    file_size: number;
    size_display: string;
    extension: string;
    changelog: string;
    created_at: string;
  } | null;
}

export interface Announcement {
  id: string;
  title: string;
  body: string;
  category?: string | null;
  category_name?: string;
  priority: 'NORMAL' | 'IMPORTANT' | 'URGENT';
  audience: string;
  department?: string | null;
  department_name?: string;
  course?: string | null;
  course_code?: string;
  target_roles: Role[];
  attachment?: string | null;
  publish_at: string;
  expires_at?: string | null;
  status: string;
  is_pinned: boolean;
  author_name: string;
  is_live: boolean;
  is_read: boolean;
  created_at: string;
}

export interface CalendarItem {
  id: string;
  title: string;
  category: string;
  start_at: string;
  end_at: string | null;
  all_day: boolean;
  location: string;
  source: 'event' | 'assignment' | 'exam' | 'holiday';
  link: string;
}

export interface NotificationItem {
  id: string;
  event: string;
  event_display: string;
  title: string;
  body: string;
  level: 'INFO' | 'SUCCESS' | 'WARNING' | 'CRITICAL';
  link: string;
  metadata: Record<string, unknown>;
  read_at: string | null;
  is_read: boolean;
  created_at: string;
}

export interface Question {
  id: string;
  course: string;
  course_code: string;
  topic?: string | null;
  topic_name?: string;
  text: string;
  question_type: string;
  type_display: string;
  difficulty: 'EASY' | 'MEDIUM' | 'HARD';
  marks: string;
  correct_answer?: string;
  explanation: string;
  tags: string[];
  status: string;
  times_used: number;
  options: { id: string; text: string; is_correct: boolean; display_order: number }[];
  created_by_name: string;
}

export interface JobPosting {
  id: string;
  title: string;
  organization: string;
  opportunity_type: string;
  type_display: string;
  work_mode: string;
  mode_display: string;
  location: string;
  description: string;
  eligibility: string;
  skills_required: string[];
  stipend_or_salary: string;
  application_url: string;
  contact_email: string;
  deadline: string | null;
  posted_by_detail?: UserBrief;
  status: string;
  view_count: number;
  is_open: boolean;
  created_at: string;
}

export interface Publication {
  id: string;
  title: string;
  authors: string;
  owner: string;
  owner_detail?: UserBrief;
  project?: string | null;
  project_title?: string;
  venue: string;
  publication_type: string;
  type_display: string;
  year: number | null;
  doi: string;
  url: string;
  abstract: string;
  citation_count: number;
  status: string;
}

export interface ResearchProject {
  id: string;
  title: string;
  abstract: string;
  principal_investigator: string;
  pi_detail?: UserBrief;
  department: string;
  department_name: string;
  research_area: string;
  funding_agency: string;
  funding_amount: string | null;
  start_date: string | null;
  expected_end_date: string | null;
  status: string;
  dataset_references: string[];
  ethics_approval_reference: string;
  milestones: {
    id: string;
    title: string;
    description: string;
    due_date: string | null;
    status: string;
  }[];
  publication_count: number;
  progress: number;
}

export interface DiscussionThread {
  id: string;
  section: string;
  course_code: string;
  author: string;
  author_detail: UserBrief;
  title: string;
  body: string;
  tags: string[];
  status: string;
  is_pinned: boolean;
  view_count: number;
  reply_count: number;
  created_at: string;
  replies?: DiscussionReply[] | null;
}

export interface DiscussionReply {
  id: string;
  thread: string;
  author: string;
  author_detail: UserBrief;
  parent?: string | null;
  body: string;
  is_accepted_answer: boolean;
  helpful_count: number;
  has_voted: boolean;
  created_at: string;
}

export interface ResourceLink {
  id: string;
  title: string;
  description: string;
  category?: string | null;
  category_name?: string;
  url: string;
  access_type: string;
  access_display: string;
  access_instructions: string;
  tags: string[];
  is_active: boolean;
  click_count: number;
}

export interface Certificate {
  id: string;
  certificate_id: string;
  holder: string;
  holder_detail?: UserBrief;
  title: string;
  description: string;
  certificate_type: string;
  type_display: string;
  issued_on: string;
  valid_until: string | null;
  department_name?: string;
  issued_by_name?: string;
  status: string;
  verification_url: string;
}

export interface AuditLog {
  id: string;
  actor: string | null;
  actor_name: string;
  actor_email: string;
  actor_role: string;
  action: string;
  action_display: string;
  object_type: string;
  object_label: string;
  description: string;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface SystemSetting {
  id: string;
  key: string;
  label: string;
  value: string;
  typed_value: unknown;
  value_type: string;
  group: string;
  description: string;
  is_public: boolean;
  is_editable: boolean;
}

export interface GradebookGrid {
  section: {
    id: string;
    course_code: string;
    course_name: string;
    name: string;
    credits: number;
  };
  components: {
    id: string;
    name: string;
    kind: string;
    max_marks: number;
    weight: number;
    is_auto_calculated: boolean;
  }[];
  students: {
    student_id: string;
    full_name: string;
    enrollment_number: string;
    cells: {
      component_id: string;
      score_id: string | null;
      marks_obtained: number | null;
      is_absent: boolean;
      status: string;
      is_locked: boolean;
    }[];
    internal_total: number;
    internal_max: number;
    external_total: number;
    total_marks: number;
    percentage: number;
    grade_letter: string;
    grade_point: number;
    is_pass: boolean;
  }[];
  internal_max: number;
}

export interface Transcript {
  semesters: {
    semester_id: string;
    semester_name: string;
    session: string;
    number: number;
    courses: {
      course_code: string;
      course_name: string;
      credits: number;
      total_marks: number;
      percentage: number;
      grade_letter: string;
      grade_point: number;
      is_pass: boolean;
    }[];
    gpa: number;
    total_credits: number;
  }[];
  cgpa: number;
  total_credits: number;
}
