# Architecture

## Shape of the system

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser (desktop / tablet / mobile, light or dark)              │
│                                                                  │
│  Next.js App Router                                              │
│   ├── (app)/*        authenticated shell: sidebar, top bar,      │
│   │                  mobile bottom nav, global search            │
│   ├── login, forgot-password, reset-password                     │
│   └── verify/certificate/[id]        ← public, no auth           │
│                                                                  │
│  AuthProvider (access token in memory)                           │
│  BrandingProvider (institution name, colours from the API)       │
│  TanStack Query (cache, retry policy, invalidation)              │
└──────────────────────────────┬───────────────────────────────────┘
                               │  JSON over HTTPS
                               │  Bearer access token (30 min)
                               │  httpOnly refresh cookie (7 days)
┌──────────────────────────────▼───────────────────────────────────┐
│  Django REST Framework — /api/v1                                 │
│                                                                  │
│  Middleware:  CORS → security → request-context (audit actor)    │
│                                                                  │
│  For every request:                                              │
│    1. JWTAuthentication resolves the user                        │
│    2. HasPerm checks the view's permission code                  │
│    3. get_queryset() narrows rows to what the user may see       │
│    4. Object-level guards catch anything addressed by id         │
│    5. Service layer computes; views never do arithmetic          │
│    6. Audit entry written for every state change                 │
└──────┬────────────────────────────────────┬──────────────────────┘
       │                                    │
┌──────▼──────────┐              ┌──────────▼──────────┐
│  PostgreSQL     │              │  Celery + Redis     │
│  (SQLite local) │              │  weekly digest      │
│                 │              │  deadline reminders │
│  UUID keys      │              │  attendance alerts  │
│  soft delete    │              │  risk snapshots     │
│  audit fields   │              │  content expiry     │
└─────────────────┘              └─────────────────────┘
```

## Design decisions

### Authorisation is enforced in four places, not one

Hiding a menu item is a convenience, never a control. Every protected endpoint
passes through:

1. **View permission** — `HasPerm` reads `required_permission` (safe methods),
   `required_write_permission` (writes) or an `action_permissions` override for
   custom actions. Codes live in `apps/core/rbac.py`.
2. **Queryset scoping** — `get_queryset()` narrows rows by role. A student's
   note list is filtered before search runs, so search cannot surface a resource
   the student could not open directly.
3. **Object-level checks** — `teaches_section()` and explicit id comparisons
   guard anything addressed by primary key, which is where IDOR lives.
4. **Serializer validation** — marks above a component maximum, negative values
   and edits to published records are refused at the boundary.

`action_permissions` exists because a custom `POST` action would otherwise
inherit the viewset's write permission. That is wrong whenever the action serves
a different audience: a student submitting feedback on a form only staff can
author, or a marker grading a submission only students can create.

### The calculation engine is the single source of truth

`apps/core/calculations.py` owns every formula: attendance percentage, weighted
component scaling, grade resolution, credit-weighted GPA and the risk score.
Views, serializers and the frontend all read from it. No percentage is computed
in a template or a React component.

Thresholds are arguments, never constants. The 75% attendance rule lives in an
`AttendancePolicy` row; grade boundaries live in `GradeBand` rows; risk weights
live in `RiskRule` rows. Changing any of them is a data edit, not a deployment.

### Configuration is data

`SystemSetting` rows carry institution name, colours, footer text and academic
parameters. Public settings are readable without authentication so the login
screen can brand itself before anyone signs in. `RolePermission` rows override
the default permission map, so an administrator can reshape a role from the
admin panel.

The default map in `rbac.py` is a fallback, not a hard-coded policy: if any
override row exists for a role, that set replaces the default entirely.

### Workflows protect academic records

Marks move `DRAFT → SUBMITTED → REVIEWED → PUBLISHED`. Publishing locks the row;
a later correction needs `marks.publish` and is written to the audit log.
Attendance sessions move `DRAFT → FINALIZED → LOCKED`. Announcements move
`DRAFT → PUBLISHED → EXPIRED`.

### The risk indicator is deliberately simple

Rule-based scoring, not a model. Each rule that fires contributes its weight and
is returned with the observed value, the threshold it crossed and guidance text.
The API response always carries the disclaimer, and the UI always renders it.

This is a design constraint, not a limitation to fix later. A staff member must
be able to audit why a student surfaced before acting. The architecture leaves
room for a learned model — `RiskSnapshot` stores the metrics alongside the
score — but the explainable path stays the default.

## Request lifecycle: marking attendance

1. Faculty opens `/attendance`; the frontend calls `/courses/my-courses`, which
   returns only sections with an active `FacultyCourseAssignment`.
2. Creating a session posts to `/attendance/sessions`. `perform_create` calls
   `teaches_section()` and refuses otherwise, then pre-creates an
   `AttendanceRecord` for every active enrolment.
3. Marking posts to `/attendance/sessions/{id}/mark`. The view rejects students
   who are not enrolled, refuses locked sessions with `409`, and writes one
   audit entry for the batch.
4. Finalising triggers `evaluate_alerts()`, which reads the department's
   `AttendancePolicy`, computes each student's percentage through the calculation
   engine and raises `AttendanceAlert` rows, avoiding duplicates.
5. Alerts fan out through `notifications.services.notify()`, which respects each
   student's per-event preferences.

## Frontend structure

- `src/lib/api.ts` — one fetch wrapper. Holds the access token in memory,
  transparently refreshes once on `401`, normalises the error envelope into
  `ApiError` with `fieldMessages` for form display.
- `src/lib/auth.tsx` — session context. On mount it exchanges the httpOnly
  refresh cookie for an access token, so a reload restores the session without
  exposing a long-lived credential to JavaScript.
- `src/components/ui/index.tsx` — the owned UI kit (shadcn/ui approach): button,
  card, table, modal, tabs, form field with label/hint/error wiring, and the
  loading, empty and error states every list view uses.
- `src/components/charts/index.tsx` — chart wrappers with one palette per theme,
  so a chart holds its contrast in both light and dark mode.
- `src/components/layout/navigation.ts` — a single nav definition filtered by
  role and permission, driving both the desktop sidebar and the mobile bottom bar.

## Extending the platform

Adding a module means adding a Django app, and the surrounding machinery comes
for free:

1. Models inherit `BaseModel` (UUID, timestamps, actor tracking, soft delete).
2. The viewset extends `AuditedModelViewSet` (actor stamping plus audit entries).
3. Permission codes are declared in `rbac.py` and mapped to roles.
4. The route registers in `config/urls.py`.
5. A nav entry in `navigation.ts` with its permission makes it appear for the
   right roles only.

Nothing in the platform hard-codes a single department or program. Every
academic entity carries a department association, so a second school is a data
migration rather than a rewrite.
