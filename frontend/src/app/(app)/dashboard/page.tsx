'use client';

import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  BookOpen,
  Briefcase,
  CalendarDays,
  ClipboardList,
  FileText,
  FlaskConical,
  GraduationCap,
  Percent,
  TrendingUp,
  Users,
} from 'lucide-react';
import Link from 'next/link';

import { CategoryBarChart, DonutChart, TrendChart, useToneColors } from '@/components/charts';
import { RiskPanel } from '@/components/risk-panel';
import {
  Alert,
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Progress,
  StatCard,
} from '@/components/ui';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { firstName, formatDate, percent, relativeTime, statusTone } from '@/lib/utils';
import type { RiskOutcome } from '@/types';

interface DashboardResponse {
  type: string;
  data: any;
  research?: { projects: number; publications: number; supervised: number };
}

export default function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardResponse>('/analytics/dashboard/me'),
  });

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  })();

  if (isLoading) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <LoadingState rows={4} />
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorState
          message="The dashboard could not be loaded. Check that the API server is running."
          onRetry={() => refetch()}
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={`${greeting}, ${firstName(user?.full_name)}`}
        description={
          user?.department_name
            ? `${user.role_display} · ${user.department_name}`
            : user?.role_display
        }
      />

      {data.type === 'student' && <StudentDashboard data={data.data} />}
      {(data.type === 'faculty' || data.type === 'scholar') && (
        <FacultyDashboard data={data.data} research={data.research} />
      )}
      {data.type === 'department' && <DepartmentDashboard data={data.data} />}
      {data.type === 'institution' && <InstitutionDashboard data={data.data} />}
      {data.type === 'alumni' && <AlumniDashboard data={data.data} />}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Student                                                                     */
/* -------------------------------------------------------------------------- */
function StudentDashboard({ data }: { data: any }) {
  const kpis = data.kpis;
  const risk: RiskOutcome = data.risk;
  const attendanceTone =
    kpis.attendance_status === 'critical'
      ? 'danger'
      : kpis.attendance_status === 'warning'
        ? 'warning'
        : 'success';

  return (
    <div className="space-y-5">
      {kpis.attendance_status !== 'ok' && (
        <Alert
          tone={kpis.attendance_status === 'critical' ? 'danger' : 'warning'}
          title={`Attendance is at ${percent(kpis.attendance_percentage)}`}
        >
          This is below the required threshold. Speak to your course coordinator about a recovery
          plan — <Link href="/attendance" className="font-medium underline">view the breakdown</Link>.
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Attendance"
          value={percent(kpis.attendance_percentage)}
          hint={`Threshold ${kpis.attendance_percentage >= 0 ? '75%' : ''}`}
          tone={attendanceTone}
          icon={Percent}
        />
        <StatCard
          label="CGPA"
          value={kpis.cgpa ? kpis.cgpa.toFixed(2) : '—'}
          hint={`${kpis.credits_earned} credits earned`}
          icon={GraduationCap}
        />
        <StatCard
          label="Enrolled courses"
          value={kpis.enrolled_courses}
          hint="This semester"
          icon={BookOpen}
        />
        <StatCard
          label="Pending work"
          value={kpis.pending_assignments}
          hint="Assignments not yet submitted"
          tone={kpis.pending_assignments > 0 ? 'warning' : 'success'}
          icon={ClipboardList}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Attendance trend</CardTitle>
            <p className="text-sm text-muted-foreground">
              Monthly attendance against the 75% requirement.
            </p>
          </CardHeader>
          <CardContent>
            {data.attendance_trend?.length ? (
              <TrendChart
                data={data.attendance_trend}
                xKey="label"
                yKey="percentage"
                label="Attendance"
                referenceValue={75}
                referenceLabel="Required"
              />
            ) : (
              <EmptyState title="No attendance recorded yet" />
            )}
          </CardContent>
        </Card>

        <RiskPanel risk={risk} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Attendance by course</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.attendance_by_course?.length ? (
              data.attendance_by_course.map((row: any) => (
                <div key={row.section_id}>
                  <div className="mb-1 flex items-baseline justify-between gap-2">
                    <span className="truncate text-sm font-medium">{row.course_code}</span>
                    <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                      {percent(row.percentage)}
                    </span>
                  </div>
                  <Progress
                    value={row.percentage}
                    tone={
                      row.status === 'critical'
                        ? 'danger'
                        : row.status === 'warning'
                          ? 'warning'
                          : 'success'
                    }
                    label={`${row.course_code} attendance`}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    {row.present + row.late} of {row.total} sessions attended
                  </p>
                </div>
              ))
            ) : (
              <EmptyState title="No attendance data yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upcoming deadlines</CardTitle>
          </CardHeader>
          <CardContent>
            {data.upcoming_assignments?.length ? (
              <ul className="divide-y divide-border">
                {data.upcoming_assignments.map((item: any) => (
                  <li key={item.id} className="py-2.5 first:pt-0 last:pb-0">
                    <Link href="/assignments" className="group block">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium group-hover:text-primary">
                            {item.title}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {item.course} · {item.max_marks} marks
                          </p>
                        </div>
                        <Badge tone="warning" className="shrink-0">
                          {relativeTime(item.due_date)}
                        </Badge>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="Nothing due"
                description="You are up to date with every published assignment."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Recent marks</CardTitle>
          </CardHeader>
          <CardContent>
            {data.recent_marks?.length ? (
              <ul className="divide-y divide-border">
                {data.recent_marks.map((mark: any, index: number) => (
                  <li key={index} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{mark.component}</p>
                      <p className="text-xs text-muted-foreground">{mark.course}</p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold tabular-nums">
                      {mark.marks ?? '—'}
                      <span className="text-muted-foreground">/{mark.max_marks}</span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No marks published yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Announcements</CardTitle>
          </CardHeader>
          <CardContent>
            {data.announcements?.length ? (
              <ul className="divide-y divide-border">
                {data.announcements.map((item: any) => (
                  <li key={item.id} className="py-2.5 first:pt-0 last:pb-0">
                    <Link href="/announcements" className="group block">
                      <div className="flex items-start gap-2">
                        <Badge tone={statusTone(item.priority)} className="mt-0.5 shrink-0">
                          {item.priority.toLowerCase()}
                        </Badge>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium group-hover:text-primary">
                            {item.title}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatDate(item.publish_at)}
                          </p>
                        </div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No announcements" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Coming up</CardTitle>
          </CardHeader>
          <CardContent>
            {data.events?.length ? (
              <ul className="divide-y divide-border">
                {data.events.map((event: any) => (
                  <li key={event.id} className="py-2.5 first:pt-0 last:pb-0">
                    <p className="truncate text-sm font-medium">{event.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(event.start_at, true)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="Nothing scheduled" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Faculty / scholar                                                           */
/* -------------------------------------------------------------------------- */
function FacultyDashboard({ data, research }: { data: any; research?: any }) {
  const kpis = data.kpis;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Sections" value={kpis.assigned_sections} hint="Assigned to you" icon={BookOpen} />
        <StatCard label="Students" value={kpis.total_students} hint="Across your sections" icon={Users} />
        <StatCard
          label="Pending grading"
          value={kpis.pending_grading}
          tone={kpis.pending_grading > 0 ? 'warning' : 'success'}
          hint="Submissions awaiting marks"
          icon={ClipboardList}
        />
        <StatCard label="Classes today" value={kpis.sessions_today} icon={CalendarDays} />
      </div>

      {research && (
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard label="Research projects" value={research.projects} icon={FlaskConical} />
          <StatCard label="Publications" value={research.publications} icon={FileText} />
          <StatCard label="Mentees" value={research.supervised} icon={Users} />
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Attendance by section</CardTitle>
            <p className="text-sm text-muted-foreground">
              Section averages against the 75% requirement.
            </p>
          </CardHeader>
          <CardContent>
            {data.sections?.length ? (
              <CategoryBarChart
                data={data.sections.map((section: any) => ({
                  ...section,
                  label: section.code,
                  status:
                    section.attendance_percentage < 65
                      ? 'critical'
                      : section.attendance_percentage < 75
                        ? 'warning'
                        : 'ok',
                }))}
                xKey="label"
                yKey="attendance_percentage"
                label="Attendance"
                colorByStatus
                referenceValue={75}
              />
            ) : (
              <EmptyState title="No sections assigned" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Today&apos;s classes</CardTitle>
          </CardHeader>
          <CardContent>
            {data.todays_classes?.length ? (
              <ul className="divide-y divide-border">
                {data.todays_classes.map((item: any) => (
                  <li key={item.id} className="flex items-center justify-between gap-2 py-2.5 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.course}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        Period {item.period}
                        {item.topic ? ` · ${item.topic}` : ''}
                      </p>
                    </div>
                    <Badge tone={item.status === 'DRAFT' ? 'warning' : 'success'}>
                      {item.status.toLowerCase()}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No sessions today"
                description="Open Attendance to start a new session."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent submissions</CardTitle>
          </CardHeader>
          <CardContent>
            {data.recent_submissions?.length ? (
              <ul className="divide-y divide-border">
                {data.recent_submissions.map((item: any) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.student}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {item.course} · {item.assignment}
                      </p>
                    </div>
                    <Badge tone={statusTone(item.status)} className="shrink-0">
                      {item.status.toLowerCase()}
                    </Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No submissions yet" />
            )}
          </CardContent>
        </Card>

        <AtRiskCard students={data.at_risk ?? []} />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Department (HOD)                                                            */
/* -------------------------------------------------------------------------- */
function DepartmentDashboard({ data }: { data: any }) {
  const kpis = data.kpis;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <StatCard label="Students" value={kpis.students} icon={Users} />
        <StatCard label="Faculty" value={kpis.faculty} icon={Users} />
        <StatCard label="Scholars" value={kpis.scholars} icon={FlaskConical} />
        <StatCard label="Courses" value={kpis.courses} icon={BookOpen} />
        <StatCard
          label="Avg attendance"
          value={percent(kpis.average_attendance)}
          tone={kpis.average_attendance < 75 ? 'warning' : 'success'}
          icon={Percent}
        />
        <StatCard
          label="Avg performance"
          value={percent(kpis.average_performance)}
          icon={TrendingUp}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Course performance</CardTitle>
            <p className="text-sm text-muted-foreground">Mean result percentage by course.</p>
          </CardHeader>
          <CardContent>
            {data.course_performance?.length ? (
              <CategoryBarChart
                data={data.course_performance}
                xKey="code"
                yKey="average"
                label="Average"
              />
            ) : (
              <EmptyState title="No results computed yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Faculty workload</CardTitle>
            <p className="text-sm text-muted-foreground">Active sections per faculty member.</p>
          </CardHeader>
          <CardContent>
            {data.faculty_workload?.length ? (
              <CategoryBarChart
                data={data.faculty_workload.map((row: any) => ({
                  ...row,
                  short: row.faculty.split(' ').slice(-1)[0],
                }))}
                xKey="short"
                yKey="sections"
                label="Sections"
                unit=""
                domain={[0, Math.max(...data.faculty_workload.map((r: any) => r.sections)) + 1]}
              />
            ) : (
              <EmptyState title="No assignments recorded" />
            )}
          </CardContent>
        </Card>
      </div>

      <AtRiskCard students={data.at_risk ?? []} />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Institution (Dean)                                                          */
/* -------------------------------------------------------------------------- */
function InstitutionDashboard({ data }: { data: any }) {
  const tones = useToneColors();
  const kpis = data.kpis;
  const riskData = Object.entries(data.risk_distribution ?? {}).map(([level, count]) => ({
    level: level.charAt(0).toUpperCase() + level.slice(1),
    count,
  }));

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
        <StatCard label="Students" value={kpis.students} icon={Users} />
        <StatCard label="Faculty" value={kpis.faculty} icon={Users} />
        <StatCard label="Scholars" value={kpis.scholars} icon={FlaskConical} />
        <StatCard label="Alumni" value={kpis.alumni} icon={GraduationCap} />
        <StatCard label="Courses" value={kpis.courses} icon={BookOpen} />
        <StatCard label="Departments" value={kpis.departments} icon={BookOpen} />
        <StatCard
          label="Avg attendance"
          value={percent(kpis.average_attendance)}
          tone={kpis.average_attendance < 75 ? 'warning' : 'success'}
          icon={Percent}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Department comparison</CardTitle>
            <p className="text-sm text-muted-foreground">
              Attendance and mean performance by department.
            </p>
          </CardHeader>
          <CardContent>
            {data.departments?.length ? (
              <CategoryBarChart
                data={data.departments}
                xKey="code"
                yKey="attendance"
                label="Attendance"
                referenceValue={75}
              />
            ) : (
              <EmptyState title="No departments configured" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Academic support distribution</CardTitle>
            <p className="text-sm text-muted-foreground">
              Students by risk indicator level.
            </p>
          </CardHeader>
          <CardContent>
            {riskData.some((row) => Number(row.count) > 0) ? (
              <DonutChart
                data={riskData}
                nameKey="level"
                valueKey="count"
                colors={[tones.ok, tones.warning, tones.high, tones.critical]}
              />
            ) : (
              <EmptyState title="No indicators raised" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Departments</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="table-scroll scrollbar-thin">
            <table className="w-full text-sm">
              <thead className="border-b border-border">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-3 font-semibold">Department</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Students</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Faculty</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Courses</th>
                  <th className="pb-2 pr-3 text-right font-semibold">Attendance</th>
                  <th className="pb-2 text-right font-semibold">Performance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.departments?.map((row: any) => (
                  <tr key={row.id}>
                    <td className="py-2.5 pr-3">
                      <span className="font-medium">{row.name}</span>
                      <span className="ml-1.5 text-xs text-muted-foreground">{row.code}</span>
                    </td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{row.students}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{row.faculty}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">{row.courses}</td>
                    <td className="py-2.5 pr-3 text-right tabular-nums">
                      {percent(row.attendance)}
                    </td>
                    <td className="py-2.5 text-right tabular-nums">{percent(row.performance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Alumni                                                                      */
/* -------------------------------------------------------------------------- */
function AlumniDashboard({ data }: { data: any }) {
  const kpis = data.kpis;
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open opportunities" value={kpis.open_opportunities} icon={Briefcase} />
        <StatCard label="My postings" value={kpis.my_postings} icon={FileText} />
        <StatCard
          label="Mentorship requests"
          value={kpis.mentorship_requests}
          tone={kpis.mentorship_requests > 0 ? 'warning' : 'default'}
          icon={Users}
        />
        <StatCard label="Upcoming events" value={kpis.upcoming_events} icon={CalendarDays} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Mentorship requests</CardTitle>
        </CardHeader>
        <CardContent>
          {data.requests?.length ? (
            <ul className="divide-y divide-border">
              {data.requests.map((item: any) => (
                <li key={item.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.requester}</p>
                    <p className="truncate text-xs text-muted-foreground">{item.topic}</p>
                  </div>
                  <Badge tone={statusTone(item.status)} className="shrink-0">
                    {item.status.toLowerCase()}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No requests yet"
              description="Enable mentorship on your alumni profile so students can reach you."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
function AtRiskCard({ students }: { students: RiskOutcome[] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle>Students who may need support</CardTitle>
            <p className="text-sm text-muted-foreground">
              Rule-based indicator for human review — never an automatic decision.
            </p>
          </div>
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
        </div>
      </CardHeader>
      <CardContent>
        {students.length ? (
          <ul className="divide-y divide-border">
            {students.slice(0, 6).map((item) => (
              <li key={item.student?.id} className="py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.student?.full_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {item.factors.map((factor) => factor.label).join(' · ') || 'No factors'}
                    </p>
                  </div>
                  <Badge tone={statusTone(item.level)} className="shrink-0">
                    {item.level_label} · {item.score}
                  </Badge>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No students flagged"
            description="Nobody currently meets the configured indicator thresholds."
          />
        )}
        <p className="mt-3 border-t border-border pt-3 text-xs text-muted-foreground">
          <Link href="/analytics" className="font-medium text-primary hover:underline">
            Open the analytics workspace
          </Link>{' '}
          to review contributing factors before acting.
        </p>
      </CardContent>
    </Card>
  );
}
