# Testing

## Running the suite

```bash
cd backend
python manage.py test apps.core.tests          # 90 tests, ~14 seconds
python manage.py test apps.core.tests -v 2     # verbose
python manage.py check                         # system checks
python manage.py makemigrations --check --dry-run

cd ../frontend
npm run typecheck                              # tsc --noEmit, strict mode
npm run build                                  # production build
npm run lint
```

## What is covered

### `test_calculations.py` — the calculation engine

Pure unit tests, no database. These cover the formulas every other feature
depends on, including the edge cases the brief calls out in section 73.

| Area | Cases |
| --- | --- |
| Attendance | Basic percentage; late counted as attended; excused removed from the denominator; zero attendance; 100% attendance; **no sessions held** (division by zero); **all sessions excused**; threshold bands; a reconfigured 85% threshold; recovery-sessions arithmetic |
| Assessment | Scaling onto a component weight; **zero component maximum**; weighted totals; percentage of a zero maximum |
| Grading | Highest matching band wins; **boundary values are inclusive** (91 → O, 90.99 → A); credit-weighted GPA; **GPA with zero credits** |
| Trends | Declining, improving and single-value series |
| Risk indicator | Healthy student scores zero; struggling student accumulates weighted factors; every factor reports observed value and threshold; **missing metrics are skipped rather than assumed**; score capped at 100; administrator rules override defaults; the disclaimer is always present |

### `test_permissions.py` — access control

Tests attack the API directly rather than checking the UI, because hiding a
button is not a control.

| Area | Cases |
| --- | --- |
| Authentication | Anonymous access refused; public endpoints reachable; **bad password and unknown account return an identical message**; disabled account cannot sign in |
| Student isolation | Cannot read a peer's marks, attendance or risk profile; **can** read their own; score list contains only their own rows; cannot list users; cannot read audit logs; cannot create a course; **cannot escalate their own role** |
| Faculty scoping | Assigned faculty can open the gradebook and register; **unassigned faculty cannot**, and cannot create a session for a section they do not teach; creating a session pre-populates the roster; faculty cannot publish marks without the permission; an admin can |
| Role boundaries | Dean sees institution analytics, faculty does not; **the Dean cannot manage users** (read-heavy by design); alumni hold no academic-record permissions and cannot reach student data; a `RolePermission` override takes effect |

### `test_workflows.py` — end-to-end behaviour and edge cases

| Area | Cases |
| --- | --- |
| Enrolment | Duplicate enrolment rejected; **capacity enforced** |
| Attendance | Duplicate session for the same date and period rejected; marking a student outside the section rejected per-row; **locked session returns 409**; invalid status rejected; percentage reflects the configured policy; a student with no sessions does not error |
| Marks | Above maximum rejected; negative rejected; valid marks stored and the result recomputed with the right grade; **published marks locked against further edits**; gradebook covers every enrolled student; an absent student scores zero without breaking the total |
| Assignments | Late submission marked `LATE`; refused when late work is disallowed; **unenrolled student cannot submit**; draft assignments invisible to students; grading above the maximum rejected |
| Uploads | Executable extension refused; disallowed extension refused; oversized refused; empty refused; **a renamed executable is caught by magic-number sniffing**; a genuine PDF accepted |
| Audit | Login and failed login recorded; **entries cannot be modified or deleted**; credentials scrubbed from metadata |
| Certificates | Public verification exposes only confirming fields; unknown id returns 404; revoked reports invalid |
| Feedback privacy | **Anonymous response stores no respondent**; participation still blocks a second submission |

## Manual verification performed

Beyond the automated suite, the running application was driven end to end:

- **All six roles** signed in and loaded their dashboards.
- **168 endpoint calls** across every navigable page for every role returned
  success — the "no broken links" check from brief section 97, done at the data
  layer.
- **Faculty attendance marking**: opened a session roster, changed a student's
  status, saved, and confirmed the register updated from 32/2 to 33/1.
- **Gradebook**: rendered 36 students against 4 weighted components with locked
  published marks.
- **Responsive**: verified at 375px with no horizontal overflow on ten pages;
  wide tables scroll inside their own containers.
- **Dark and light themes**: chart palettes swap so contrast holds in both.

## Bugs this process caught

Worth recording, because they justify the effort:

| Found by | Bug |
| --- | --- |
| Test suite | Custom `POST` actions inherited the viewset's **write** permission, so faculty could not grade submissions and students could not submit feedback, register for events, mark notices read or follow e-resource links. Fixed by adding `action_permissions` to `HasPerm` |
| Route sweep | Alumni saw Attendance and Marks navigation items despite having no academic record. Fixed by splitting `_ACADEMIC_BASE` out of the common permission baseline |
| Browser check | The donut chart rendered empty sector groups — Recharts 2.x pie mount-animation does not complete under React 19. Fixed with `isAnimationActive={false}` |
| Browser check | Chart palette was fixed rather than theme-aware, so series colours lost contrast in dark mode. Fixed with per-theme ramps |
| Browser check | CGPA showed as "—" because seeded `CourseResult` rows were never marked published |
| Browser check | The greeting read "Good afternoon, Dr." — naive `split(' ')[0]` on names with honorifics |

## Not covered

Stated plainly rather than implied:

- No frontend component tests (Jest/React Testing Library) or Playwright E2E
  suite. Frontend verification was manual and browser-driven.
- No load or performance testing.
- No accessibility audit with axe or a screen reader. Semantic HTML, ARIA
  attributes, focus states, labelled controls and keyboard operability were
  built in and spot-checked, but not formally audited.
- No security penetration test.

## Adding tests

Backend tests live in `apps/core/tests/`. Extend the existing
`AccessControlTestCase` or `WorkflowTestCase` base classes, which build a
department, session, semester, course, section, faculty and students once per
class via `setUpTestData`.

When adding a feature, the tests that matter most are:

1. Can a user without the permission reach it?
2. Can a user reach *another* user's instance of it?
3. What happens at zero, at the maximum, and one past the maximum?
