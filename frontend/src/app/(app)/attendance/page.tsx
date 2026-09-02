'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarPlus, Check, Download, Lock, Percent, Save } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { CategoryBarChart, TrendChart } from '@/components/charts';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  Progress,
  Select,
  StatCard,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
} from '@/components/ui';
import { ApiError, api, downloadFile } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate, percent } from '@/lib/utils';
import type { AttendanceSummary, CourseAttendance, CourseSection } from '@/types';

export default function AttendancePage() {
  const { hasRole, can } = useAuth();
  const isStaff = can('attendance.mark');

  return (
    <>
      <PageHeader
        title="Attendance"
        description={
          isStaff
            ? 'Mark sessions, review registers and export reports.'
            : 'Your attendance across every enrolled course.'
        }
      />
      {isStaff ? <StaffAttendance /> : <StudentAttendance />}
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Student view                                                                */
/* -------------------------------------------------------------------------- */
function StudentAttendance() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['attendance', 'me'],
    queryFn: () =>
      api.get<{
        overall: AttendanceSummary;
        by_course: CourseAttendance[];
        monthly_trend: { month: string; label: string; percentage: number; sessions: number }[];
      }>('/attendance/summary/me'),
  });

  if (isLoading) return <LoadingState rows={4} />;
  if (error || !data) {
    return <ErrorState message="Attendance could not be loaded." onRetry={() => refetch()} />;
  }

  const { overall, by_course: byCourse, monthly_trend: trend } = data;
  const tone =
    overall.status === 'critical' ? 'danger' : overall.status === 'warning' ? 'warning' : 'success';

  return (
    <div className="space-y-5">
      {overall.status !== 'ok' && (
        <Alert tone={tone === 'danger' ? 'danger' : 'warning'} title="Attendance needs attention">
          You are at {percent(overall.percentage)} against a {overall.warning_threshold}%
          requirement.{' '}
          {overall.sessions_to_reach_threshold > 0 && (
            <>
              Attending the next {overall.sessions_to_reach_threshold} consecutive session
              {overall.sessions_to_reach_threshold === 1 ? '' : 's'} would bring you back to the
              threshold.
            </>
          )}
        </Alert>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Overall attendance"
          value={percent(overall.percentage)}
          tone={tone}
          hint={`Requirement ${overall.warning_threshold}%`}
          icon={Percent}
        />
        <StatCard label="Sessions attended" value={overall.present + overall.late} />
        <StatCard label="Absent" value={overall.absent} tone={overall.absent > 0 ? 'warning' : 'default'} />
        <StatCard label="Excused" value={overall.excused} hint="Not counted against you" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Monthly trend</CardTitle>
        </CardHeader>
        <CardContent>
          {trend.length ? (
            <TrendChart
              data={trend}
              xKey="label"
              yKey="percentage"
              label="Attendance"
              referenceValue={overall.warning_threshold}
              referenceLabel="Required"
            />
          ) : (
            <EmptyState title="No sessions recorded yet" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>By course</CardTitle>
        </CardHeader>
        <CardContent>
          {byCourse.length === 0 ? (
            <EmptyState title="No attendance recorded" />
          ) : (
            <div className="space-y-4">
              {byCourse.map((row) => (
                <div key={row.section_id}>
                  <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
                    <div className="min-w-0">
                      <span className="font-mono text-xs text-muted-foreground">
                        {row.course_code}
                      </span>
                      <span className="ml-2 text-sm font-medium">{row.course_name}</span>
                    </div>
                    <Badge
                      tone={
                        row.status === 'critical'
                          ? 'danger'
                          : row.status === 'warning'
                            ? 'warning'
                            : 'success'
                      }
                    >
                      {percent(row.percentage)}
                    </Badge>
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
                    {row.present} present · {row.late} late · {row.absent} absent · {row.excused}{' '}
                    excused (of {row.total})
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Staff view                                                                  */
/* -------------------------------------------------------------------------- */
interface SectionRegister {
  section: { id: string; course_code: string; course_name: string; name: string };
  policy: { warning_threshold: string; critical_threshold: string };
  total_sessions: number;
  students: (AttendanceSummary & {
    student_id: string;
    full_name: string;
    enrollment_number: string;
  })[];
}

function StaffAttendance() {
  const queryClient = useQueryClient();
  const [sectionId, setSectionId] = useState<string>('');
  const [creating, setCreating] = useState(false);
  const [markingSession, setMarkingSession] = useState<string | null>(null);

  const sectionsQuery = useQuery({
    queryKey: ['my-courses'],
    queryFn: () => api.get<CourseSection[]>('/courses/my-courses'),
  });

  const sections = sectionsQuery.data ?? [];
  const activeSection = sectionId || sections[0]?.id || '';

  const registerQuery = useQuery({
    queryKey: ['attendance-register', activeSection],
    queryFn: () => api.get<SectionRegister>(`/attendance/summary/section/${activeSection}`),
    enabled: Boolean(activeSection),
  });

  const sessionsQuery = useQuery({
    queryKey: ['attendance-sessions', activeSection],
    queryFn: () =>
      api.get<{ results: any[] }>(`/attendance/sessions?section=${activeSection}&page_size=20`),
    enabled: Boolean(activeSection),
  });

  const createSession = useMutation({
    mutationFn: (payload: { section: string; date: string; period: number; topic: string }) =>
      api.post('/attendance/sessions', payload),
    onSuccess: () => {
      toast.success('Session created — mark the roster below.');
      setCreating(false);
      queryClient.invalidateQueries({ queryKey: ['attendance-sessions', activeSection] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Could not create the session.'),
  });

  if (sectionsQuery.isLoading) return <LoadingState rows={4} />;
  if (sections.length === 0) {
    return (
      <EmptyState
        title="No sections assigned"
        description="You are not currently assigned to teach any course section."
      />
    );
  }

  const register = registerQuery.data;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Select
          value={activeSection}
          onChange={(event) => setSectionId(event.target.value)}
          aria-label="Select a section"
          className="sm:max-w-sm"
        >
          {sections.map((section) => (
            <option key={section.id} value={section.id}>
              {section.course_code} — {section.course_name} (Sec {section.name})
            </option>
          ))}
        </Select>
        <div className="flex gap-2">
          <Button onClick={() => setCreating(true)}>
            <CalendarPlus className="h-4 w-4" aria-hidden />
            New session
          </Button>
          <Button
            variant="outline"
            onClick={() =>
              downloadFile(
                `/exports/attendance/${activeSection}`,
                `attendance-${register?.section.course_code ?? 'section'}.csv`,
              ).catch((error) =>
                toast.error(error instanceof ApiError ? error.message : 'Export failed.'),
              )
            }
          >
            <Download className="h-4 w-4" aria-hidden />
            Export
          </Button>
        </div>
      </div>

      {sessionsQuery.data?.results && sessionsQuery.data.results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Date</TH>
                  <TH>Period</TH>
                  <TH>Topic</TH>
                  <TH>Present</TH>
                  <TH>Absent</TH>
                  <TH>Status</TH>
                  <TH className="text-right">Action</TH>
                </TR>
              </THead>
              <TBody>
                {sessionsQuery.data.results.slice(0, 8).map((session: any) => (
                  <TR key={session.id}>
                    <TD className="whitespace-nowrap">{formatDate(session.date)}</TD>
                    <TD>{session.period}</TD>
                    <TD className="max-w-[220px] truncate">{session.topic || '—'}</TD>
                    <TD className="tabular-nums">{session.record_summary?.present ?? 0}</TD>
                    <TD className="tabular-nums">{session.record_summary?.absent ?? 0}</TD>
                    <TD>
                      <Badge
                        tone={
                          session.status === 'LOCKED'
                            ? 'muted'
                            : session.status === 'FINALIZED'
                              ? 'success'
                              : 'warning'
                        }
                      >
                        {session.status.toLowerCase()}
                      </Badge>
                    </TD>
                    <TD className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={session.status === 'LOCKED'}
                        onClick={() => setMarkingSession(session.id)}
                      >
                        {session.status === 'LOCKED' ? (
                          <Lock className="h-3.5 w-3.5" aria-hidden />
                        ) : (
                          'Mark'
                        )}
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Register</CardTitle>
          {register && (
            <p className="text-sm text-muted-foreground">
              {register.total_sessions} sessions held · warning below{' '}
              {register.policy.warning_threshold}%
            </p>
          )}
        </CardHeader>
        <CardContent>
          {registerQuery.isLoading && <LoadingState rows={3} />}
          {registerQuery.error && (
            <ErrorState
              message="The register could not be loaded."
              onRetry={() => registerQuery.refetch()}
            />
          )}
          {register && register.students.length === 0 && (
            <EmptyState title="No students enrolled in this section" />
          )}
          {register && register.students.length > 0 && (
            <>
              <div className="mb-5">
                <CategoryBarChart
                  data={register.students.slice(0, 15).map((student) => ({
                    label: student.enrollment_number.slice(-4),
                    percentage: student.percentage,
                    status: student.status,
                  }))}
                  xKey="label"
                  yKey="percentage"
                  label="Attendance"
                  colorByStatus
                  referenceValue={Number(register.policy.warning_threshold)}
                  height={220}
                />
              </div>
              <Table>
                <THead>
                  <TR>
                    <TH>Enrolment</TH>
                    <TH>Student</TH>
                    <TH className="text-right">Present</TH>
                    <TH className="text-right">Absent</TH>
                    <TH className="text-right">Late</TH>
                    <TH className="text-right">Attendance</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {register.students.map((student) => (
                    <TR key={student.student_id}>
                      <TD className="whitespace-nowrap font-mono text-xs">
                        {student.enrollment_number}
                      </TD>
                      <TD className="max-w-[200px] truncate">{student.full_name}</TD>
                      <TD className="text-right tabular-nums">{student.present}</TD>
                      <TD className="text-right tabular-nums">{student.absent}</TD>
                      <TD className="text-right tabular-nums">{student.late}</TD>
                      <TD className="text-right font-medium tabular-nums">
                        {percent(student.percentage)}
                      </TD>
                      <TD>
                        <Badge
                          tone={
                            student.status === 'critical'
                              ? 'danger'
                              : student.status === 'warning'
                                ? 'warning'
                                : 'success'
                          }
                        >
                          {student.status}
                        </Badge>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>

      <CreateSessionModal
        open={creating}
        onClose={() => setCreating(false)}
        sectionId={activeSection}
        onSubmit={(payload) => createSession.mutate(payload)}
        loading={createSession.isPending}
      />

      {markingSession && (
        <MarkRosterModal
          sessionId={markingSession}
          sectionId={activeSection}
          onClose={() => setMarkingSession(null)}
        />
      )}
    </div>
  );
}

function CreateSessionModal({
  open,
  onClose,
  sectionId,
  onSubmit,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  sectionId: string;
  onSubmit: (payload: { section: string; date: string; period: number; topic: string }) => void;
  loading: boolean;
}) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [period, setPeriod] = useState(1);
  const [topic, setTopic] = useState('');

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New attendance session"
      description="A row is created for every enrolled student, defaulting to present."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={loading}
            onClick={() => onSubmit({ section: sectionId, date, period, topic })}
          >
            Create session
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Date" required>
          {(props) => (
            <Input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              {...props}
            />
          )}
        </Field>
        <Field label="Period" hint="Period number within the teaching day." required>
          {(props) => (
            <Input
              type="number"
              min={1}
              max={12}
              value={period}
              onChange={(event) => setPeriod(Number(event.target.value))}
              {...props}
            />
          )}
        </Field>
        <Field label="Topic">
          {(props) => (
            <Input
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="e.g. Measures of association"
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}

const STATUS_OPTIONS = ['PRESENT', 'ABSENT', 'LATE', 'EXCUSED'] as const;

function MarkRosterModal({
  sessionId,
  sectionId,
  onClose,
}: {
  sessionId: string;
  sectionId: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [statuses, setStatuses] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ['attendance-roster', sessionId],
    queryFn: () => api.get<any>(`/attendance/sessions/${sessionId}/roster`),
  });

  const save = useMutation({
    mutationFn: (finalize: boolean) =>
      api.post(`/attendance/sessions/${sessionId}/mark`, {
        records: (data?.records ?? []).map((record: any) => ({
          student: record.student,
          status: statuses[record.student] ?? record.status,
        })),
        finalize,
      }),
    onSuccess: (result: any) => {
      toast.success(
        `Attendance saved for ${result.updated} students` +
          (result.alerts_generated ? ` · ${result.alerts_generated} alerts raised` : ''),
      );
      queryClient.invalidateQueries({ queryKey: ['attendance-register', sectionId] });
      queryClient.invalidateQueries({ queryKey: ['attendance-sessions', sectionId] });
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Attendance could not be saved.'),
  });

  const setAll = (value: string) => {
    const next: Record<string, string> = {};
    (data?.records ?? []).forEach((record: any) => {
      next[record.student] = value;
    });
    setStatuses(next);
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Mark attendance"
      description={
        data?.session
          ? `${data.session.course_code} · ${formatDate(data.session.date)} · Period ${data.session.period}`
          : undefined
      }
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate(false)}>
            <Save className="h-4 w-4" aria-hidden />
            Save draft
          </Button>
          <Button loading={save.isPending} onClick={() => save.mutate(true)}>
            <Check className="h-4 w-4" aria-hidden />
            Save and finalise
          </Button>
        </>
      }
    >
      {isLoading ? (
        <LoadingState rows={5} />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            <span className="text-sm text-muted-foreground">Mark everyone:</span>
            {STATUS_OPTIONS.map((option) => (
              <Button key={option} size="sm" variant="outline" onClick={() => setAll(option)}>
                {option.toLowerCase()}
              </Button>
            ))}
          </div>
          <ul className="divide-y divide-border">
            {(data?.records ?? []).map((record: any) => {
              const current = statuses[record.student] ?? record.status;
              return (
                <li
                  key={record.id}
                  className="flex flex-col gap-2 py-2.5 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {record.student_detail?.full_name}
                    </p>
                    <p className="font-mono text-xs text-muted-foreground">
                      {record.enrollment_number}
                    </p>
                  </div>
                  <div
                    role="radiogroup"
                    aria-label={`Attendance for ${record.student_detail?.full_name}`}
                    className="flex flex-wrap gap-1"
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <button
                        key={option}
                        type="button"
                        role="radio"
                        aria-checked={current === option}
                        onClick={() =>
                          setStatuses((previous) => ({ ...previous, [record.student]: option }))
                        }
                        className={`rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                          current === option
                            ? option === 'PRESENT'
                              ? 'border-success bg-success/10 text-success'
                              : option === 'ABSENT'
                                ? 'border-destructive bg-destructive/10 text-destructive'
                                : option === 'LATE'
                                  ? 'border-warning bg-warning/10 text-warning'
                                  : 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground hover:bg-muted'
                        }`}
                      >
                        {option.charAt(0) + option.slice(1).toLowerCase()}
                      </button>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Modal>
  );
}
