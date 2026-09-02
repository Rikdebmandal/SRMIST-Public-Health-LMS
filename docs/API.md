# API reference

Base URL: `/api/v1`. Interactive documentation: `/api/docs/`. OpenAPI schema:
`/api/schema/`.

## Conventions

- Paths carry **no trailing slash** — `GET /api/v1/courses`.
- All requests and responses are JSON, except file uploads (multipart) and CSV
  exports.
- Authentication is a bearer token: `Authorization: Bearer <access>`.
- Timestamps are ISO 8601 with offset, rendered in `Asia/Kolkata` by default.

### Pagination

List endpoints return:

```json
{
  "count": 143,
  "page": 1,
  "page_size": 20,
  "total_pages": 8,
  "next": "http://localhost:8000/api/v1/courses?page=2",
  "previous": null,
  "results": []
}
```

Controlled by `?page=` and `?page_size=` (max 200). Some small collections
(settings, grade scales, policies) are unpaginated and return a bare array.

### Filtering, search and ordering

```
GET /api/v1/courses?department=<uuid>&semester_number=1&status=ACTIVE
GET /api/v1/notes?search=epidemiology
GET /api/v1/assignments?ordering=-due_date
```

### Error envelope

Every failure has the same shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The submitted data is invalid.",
    "details": { "marks_obtained": ["Marks cannot exceed the component maximum of 20."] }
  }
}
```

| Status | Code | Meaning |
| --- | --- | --- |
| 400 | `bad_request`, `validation_error` | Malformed or invalid input |
| 401 | `authentication_required`, `invalid_credentials`, `session_expired` | Not signed in |
| 403 | `permission_denied`, `account_disabled` | Signed in, not allowed |
| 404 | `not_found` | Absent, or not visible to this user |
| 409 | `conflict` | Duplicate, or a locked record |
| 422 | `validation_error` | Model-level validation failure |
| 429 | `rate_limited`, `account_locked` | Throttled or locked out |
| 500 | `server_error` | Logged server-side; no stack trace is returned |

`404` is returned for records outside a user's scope, so ids cannot be probed
for existence.

---

## Authentication

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/login` | `{email, password}` → `{access, user}` and sets the httpOnly refresh cookie. Throttled 10/min |
| POST | `/auth/refresh` | Reads the cookie, returns a rotated `{access, user}` |
| POST | `/auth/logout` | Blacklists the refresh token, clears the cookie |
| GET | `/auth/me` | The current user with effective permissions |
| PATCH | `/auth/me` | Update preferences: phone, bio, theme, timezone |
| POST | `/auth/password/change` | `{current_password, new_password}` |
| POST | `/auth/password/reset` | `{email}`. Always the same response, whether or not the account exists |
| POST | `/auth/password/reset/confirm` | `{token, new_password}` |

Five failed attempts within the lockout window return `429` with
`account_locked`.

The user payload includes a `permissions` array. The frontend uses it to shape
navigation; the server checks independently on every request.

---

## Endpoint map

### People and structure

| Path | Read | Write |
| --- | --- | --- |
| `/users` | `user.view` | `user.manage` |
| `/users/{id}/activate`, `/deactivate`, `/reset-password` | — | `user.manage` |
| `/users/{id}/change-role` | — | `role.manage` |
| `/roles/permissions`, `/roles/permissions/catalogue`, `/bulk-set` | `role.manage` | `role.manage` |
| `/departments` | `department.view` | `department.manage` |
| `/programs`, `/academic-sessions`, `/semesters`, `/batches`, `/curriculum`, `/holidays` | `department.view` | `academic.manage` |
| `/curriculum/by-program?program=<uuid>` | `course.view` | — |

### Courses

| Path | Read | Write |
| --- | --- | --- |
| `/courses`, `/course-types`, `/sections` | `course.view` | `course.manage` |
| `/courses/my-courses` | `course.view` | — |
| `/courses/{id}/sections`, `/sections/{id}/students` | `course.view` | — |
| `/faculty-assignments` | `course.view` | `course.manage` |
| `/enrollments`, `/enrollments/bulk` | `course.view` | `enrollment.manage` |

### Teaching

| Path | Read | Write |
| --- | --- | --- |
| `/notes` | `note.view` | `note.manage` |
| `/notes/upload`, `/notes/{id}/versions` | — | `note.manage` (throttled 120/hr) |
| `/notes/{id}/download`, `/notes/{id}/view` | `note.view` | — |
| `/questions`, `/question-topics`, `/questions/statistics` | `question.view` | `question.manage` |
| `/questions/generate-paper` | — | `question.manage` |
| `/assignments`, `/assignments/{id}/publish` | `assignment.view` | `assignment.manage` |
| `/assignments/{id}/submissions` | assigned faculty only | — |
| `/submissions` | `assignment.view` | `assignment.submit` |
| `/submissions/{id}/grade` | — | `assignment.grade` |

### Attendance

| Path | Read | Write |
| --- | --- | --- |
| `/attendance/policies` | `attendance.view_own` | `attendance.configure` |
| `/attendance/sessions` | `attendance.view_all` | `attendance.mark` |
| `/attendance/sessions/{id}/roster` | assigned faculty | — |
| `/attendance/sessions/{id}/mark` | — | `attendance.mark` |
| `/attendance/sessions/{id}/lock` | — | `attendance.configure` |
| `/attendance/summary/me` | any signed-in student | — |
| `/attendance/summary/student/{id}` | self, or `attendance.view_all` | — |
| `/attendance/summary/section/{id}` | assigned faculty | — |
| `/attendance/alerts`, `/{id}/acknowledge` | own alerts, or `attendance.view_all` | `attendance.view_own` |

Marking payload:

```json
{
  "records": [
    {"student": "<uuid>", "status": "PRESENT", "remarks": ""},
    {"student": "<uuid>", "status": "ABSENT"}
  ],
  "finalize": true
}
```

Statuses: `PRESENT`, `ABSENT`, `LATE`, `EXCUSED`. Students outside the section
are reported in `rejected` rather than failing the batch. `finalize: true`
triggers alert evaluation.

### Assessment

| Path | Read | Write |
| --- | --- | --- |
| `/assessment-components` | `marks.view_own` | `marks.configure` |
| `/scores` | own published rows, or `marks.view_all` | `marks.enter` |
| `/scores/bulk` | — | `marks.enter` |
| `/scores/publish` | — | `marks.publish` |
| `/external-marks` | own published rows, or `marks.view_all` | `marks.enter_external` |
| `/grade-scales`, `/grade-bands` | `marks.view_own` | `marks.configure` |
| `/gradebook/me` | any student | — |
| `/gradebook/section/{id}` | assigned faculty | — |
| `/gradebook/student/{id}` | self, or `marks.view_all` | — |
| `/gradebook/recompute` | — | `marks.enter` |

Bulk entry reports per-row outcomes rather than failing wholesale:

```json
{
  "updated": 34,
  "rejected": [{"student": "<uuid>", "reason": "Marks are published and locked."}]
}
```

### Communication

| Path | Read | Write |
| --- | --- | --- |
| `/announcements`, `/announcements/feed` | `announcement.view` | `announcement.manage` |
| `/announcements/{id}/publish` | — | `announcement.manage` |
| `/announcements/{id}/mark-read` | — | `announcement.view` |
| `/notifications`, `/unread-count`, `/{id}/read`, `/read-all` | own only | own only |
| `/notification-preferences`, `/catalogue`, `/bulk` | own only | own only |
| `/notification-templates` | `settings.manage` | `settings.manage` |
| `/digest/subscription`, `/digest/preview` | own only | own only |
| `/events`, `/events/agenda` | `event.view` | `event.manage` |
| `/events/{id}/register`, `/cancel-registration` | — | `event.view` |
| `/threads`, `/replies` | `forum.participate` | `forum.participate` |
| `/threads/{id}/pin`, `/hide` | — | `forum.moderate` |
| `/replies/{id}/helpful`, `/accept` | — | `forum.participate` |
| `/feedback/forms` | `feedback.submit` | `feedback.manage` |
| `/feedback/forms/{id}/submit` | — | `feedback.submit` |
| `/feedback/forms/{id}/results` | `feedback.manage` | — |

`/events/agenda?from=&to=` merges stored events with projected assignment
deadlines, examination windows and holidays into one sorted feed.

Anonymous feedback results are withheld until at least three responses exist, so
an individual answer cannot be inferred.

### Analytics

| Path | Read |
| --- | --- |
| `/analytics/dashboard/me` | any signed-in user; shape depends on role |
| `/analytics/dashboard/department/{id}` | `analytics.view_department` |
| `/analytics/dashboard/institution` | `analytics.view_institution` |
| `/analytics/workspace/attendance-vs-performance` | `analytics.view_course` |
| `/analytics/workspace/grade-distribution` | `analytics.view_course` |
| `/analytics/workspace/submission-rates` | `analytics.view_course` |
| `/analytics/workspace/engagement` | `analytics.view_course` |
| `/analytics/risk/me` | any signed-in student |
| `/analytics/risk/students?level=` | `risk.view` |
| `/analytics/risk/student/{id}` | self, or `risk.view` |
| `/analytics/risk-rules`, `/defaults` | `risk.view` / `risk.configure` to write |
| `/analytics/risk-snapshots`, `/{id}/review` | `risk.view` |

Every risk response carries `indicator_name`, `disclaimer` and a `factors` array
in which each entry states the observed value, the threshold crossed, the weight
contributed and guidance text.

### Research, alumni and careers

| Path | Read | Write |
| --- | --- | --- |
| `/research/projects`, `/mine`, `/milestones` | `research.view` | `research.manage` |
| `/research/publications`, `/statistics`, `/conferences` | `research.view` | `research.manage` |
| `/alumni/profiles` | `alumni.view` (directory-visible rows only) | `alumni.manage` |
| `/mentorship`, `/{id}/respond` | own requests only | `mentorship.participate` |
| `/jobs`, `/jobs/open` | `job.view` | `job.manage` |

### Platform

| Path | Read | Write |
| --- | --- | --- |
| `/library/resources`, `/categories`, `/{id}/visit` | `library.view` | `library.manage` |
| `/certificates`, `/{id}/revoke` | own, or `certificate.manage` | `certificate.manage` |
| `/verify/certificate/{certificate_id}` | **public, no auth** | — |
| `/audit-logs`, `/actions`, `/summary` | `audit.view` | read-only by design |
| `/settings`, `/settings/bulk` | `settings.manage` | `settings.manage` |
| `/settings/public` | **public, no auth** | — |
| `/dashboard-widgets`, `/for-me` | `settings.manage` | `settings.manage` |
| `/search?q=` | any signed-in user, scoped to their permissions | — |
| `/health` | **public, no auth** | — |

### Exports

CSV, permission-checked before a row is written, and recorded in the audit log.

| Path | Requires |
| --- | --- |
| `/exports/attendance/{section_id}` | `report.export` + assigned to the section |
| `/exports/gradebook/{section_id}` | `report.export` + assigned to the section |
| `/exports/students` | `report.export` + `user.view` |
| `/exports/at-risk` | `risk.view` |

---

## Worked example: publishing an assignment

```bash
# 1. Sign in
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"faculty1@sph.srmist.demo","password":"Demo@12345"}'

# 2. Find your sections
curl -s http://localhost:8000/api/v1/courses/my-courses \
  -H "Authorization: Bearer $ACCESS"

# 3. Create the assignment
curl -s -X POST http://localhost:8000/api/v1/assignments \
  -H "Authorization: Bearer $ACCESS" -H 'Content-Type: application/json' \
  -d '{"section":"<uuid>","title":"Assignment 3","max_marks":20,
       "due_date":"2026-10-15T23:59:00+05:30","allowed_extensions":["pdf"]}'

# 4. Publish — this notifies every enrolled student
curl -s -X POST http://localhost:8000/api/v1/assignments/<id>/publish \
  -H "Authorization: Bearer $ACCESS"
```
