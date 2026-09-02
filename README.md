# Public Health LMS

A Learning Management System for the **School of Public Health**, SRM Institute of
Science and Technology.

Built as an academic project for the M.Sc. Health Data Science program. All data
in the demonstration dataset is fictional — no real student records are used.

---

## What it does

| Area | Capability |
| --- | --- |
| Identity | Email/JWT authentication, six roles, database-configurable RBAC, brute-force lockout, audited password resets |
| Academics | Departments, programs, academic sessions, semesters, batches, curriculum, courses, sections, enrolment |
| Teaching | Versioned note repository, reusable question bank, assignments with late-submission rules |
| Assessment | Configurable internal components, external marks, gradebook, draft → published → locked workflow, GPA/CGPA |
| Attendance | Session marking, configurable thresholds, alerts, per-course and monthly analysis |
| Engagement | Targeted announcements, notifications, unified calendar, discussion forum, feedback forms, weekly digest |
| Analytics | Role dashboards, attendance-vs-performance workspace, explainable academic support indicator |
| Research & alumni | Projects, milestones, publications, alumni directory, mentorship, jobs board |
| Platform | E-resource directory, verifiable certificates, immutable audit log, branding and settings admin |

## Stack

- **Frontend** — Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, TanStack Query, React Hook Form + Zod, Recharts
- **Backend** — Django 5.1, Django REST Framework, SimpleJWT, drf-spectacular
- **Database** — PostgreSQL in production, SQLite for zero-config local development
- **Jobs & cache** — Celery + Redis (tasks run inline when Redis is absent)

---

## Quick start

Two terminals. Nothing to install beyond Python 3.10+ and Node 20+.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --reset
python manage.py runserver 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**.

### Demonstration accounts

Every account uses the password `Demo@12345`.

| Role | Email |
| --- | --- |
| Dean | `dean@sph.srmist.demo` |
| HOD / Staff admin | `hod@sph.srmist.demo` |
| Faculty | `faculty1@sph.srmist.demo` |
| Research scholar | `scholar1@sph.srmist.demo` |
| Student | `student1@sph.srmist.demo` |
| Alumni | `alumni1@sph.srmist.demo` |

The login screen has a one-tap chip for each of these.

> `student1` is deliberately seeded as a struggling student so the attendance
> warnings and the Academic Support Risk Indicator have something to show.
> `student3` onwards are healthier.

---

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts PostgreSQL, Redis, the Django API, a Celery worker, the Celery beat
scheduler and the Next.js frontend. Seed the demo data once the stack is up:

```bash
docker compose exec backend python manage.py seed_demo --reset
```

---

## Project layout

```
public-health-lms/
├── backend/
│   ├── config/               # settings, URLs, Celery
│   ├── apps/
│   │   ├── core/             # base models, RBAC, calculation engine, tests
│   │   ├── accounts/         # users, roles, profiles
│   │   ├── academics/        # departments, programs, sessions, curriculum
│   │   ├── courses/          # courses, sections, faculty assignment, enrolment
│   │   ├── documents/        # notes with versioning
│   │   ├── question_bank/    # topics and questions
│   │   ├── assignments/      # assignments and submissions
│   │   ├── attendance/       # policy, sessions, records, alerts
│   │   ├── assessments/      # components, scores, grading, results
│   │   ├── announcements/    # targeted notices
│   │   ├── notifications/    # in-app/email, preferences, templates, digest
│   │   ├── calendarapp/      # unified calendar
│   │   ├── analytics/        # dashboards and the risk indicator
│   │   ├── research/         # projects, milestones, publications
│   │   ├── alumni/           # mentorship and the jobs board
│   │   ├── forums/           # course discussions
│   │   ├── feedback/         # configurable feedback forms
│   │   ├── library/          # e-resource directory
│   │   ├── certificates/     # issuing and public verification
│   │   ├── auditlogs/        # immutable audit trail
│   │   └── settings_app/     # system settings and dashboard widgets
│   └── manage.py
├── frontend/
│   └── src/
│       ├── app/              # routes (App Router)
│       ├── components/       # UI kit, layout shell, charts
│       ├── lib/              # API client, auth, branding, helpers
│       └── types/            # shared TypeScript models
├── docs/                     # architecture, database, API, security, deployment
├── docker/                   # Dockerfiles
└── docker-compose.yml
```

---

## Documentation

| Document | Contents |
| --- | --- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, request flow, module boundaries |
| [DATABASE.md](docs/DATABASE.md) | ERD, entities, constraints, migration and seed strategy |
| [API.md](docs/API.md) | Endpoint reference, conventions, error envelope |
| [SECURITY.md](docs/SECURITY.md) | Threat model, controls, privacy posture |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Environment variables, production deployment, backups |
| [TESTING.md](docs/TESTING.md) | Test strategy, how to run, what is covered |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Conventions for extending the platform |

Interactive API documentation runs at **http://localhost:8000/api/docs/** once
the backend is up.

---

## Commands

```bash
# Backend
python manage.py test apps.core.tests    # 90 automated tests
python manage.py check                   # system checks
python manage.py makemigrations --check  # detect model drift
python manage.py seed_demo --reset       # rebuild demo data

# Frontend
npm run typecheck                        # tsc --noEmit
npm run build                            # production build
npm run lint
```

---

## Known limitations

- Email is written to the console in development; configure SMTP for real delivery.
- The at-risk scan is bounded to 300 students per request. Beyond that, move the
  evaluation into the Celery task and read stored `RiskSnapshot` rows instead.
- Bulk CSV import is exposed as an API pattern but has no dedicated UI screen yet.
- Push notifications are modelled in the preference system but no service worker
  subscription flow is wired up.
- The PWA ships a manifest and installable shell; it does not cache API data for
  offline use, and does not claim to.

## Licence

Academic project. Not an official SRMIST production system.
