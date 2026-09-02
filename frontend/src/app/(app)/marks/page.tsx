'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, GraduationCap, Lock, Send } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

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
  Input,
  LoadingState,
  PageHeader,
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
import { percent } from '@/lib/utils';
import type { CourseSection, GradebookGrid, Transcript } from '@/types';

export default function MarksPage() {
  const { can } = useAuth();
  const isStaff = can('marks.enter');

  return (
    <>
      <PageHeader
        title={isStaff ? 'Gradebook' : 'My marks'}
        description={
          isStaff
            ? 'Enter, review and publish internal assessment marks.'
            : 'Published marks and your academic transcript.'
        }
      />
      {isStaff ? <FacultyGradebook /> : <StudentMarks />}
    </>
  );
}

/* -------------------------------------------------------------------------- */
function StudentMarks() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['gradebook', 'me'],
    queryFn: () => api.get<{ courses: any[]; transcript: Transcript }>('/gradebook/me'),
  });

  if (isLoading) return <LoadingState rows={4} />;
  if (error || !data) {
    return <ErrorState message="Marks could not be loaded." onRetry={() => refetch()} />;
  }

  const { courses, transcript } = data;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="CGPA"
          value={transcript.cgpa ? transcript.cgpa.toFixed(2) : '—'}
          hint="Credit-weighted across semesters"
          icon={GraduationCap}
        />
        <StatCard label="Credits earned" value={transcript.total_credits} />
        <StatCard label="Courses with results" value={courses.length} />
      </div>

      {courses.length === 0 ? (
        <EmptyState
          title="No marks published yet"
          description="Marks appear here once your faculty publishes them."
        />
      ) : (
        <div className="space-y-4">
          {courses.map((course) => (
            <Card key={course.section_id}>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <CardTitle>
                      <span className="font-mono text-sm text-muted-foreground">
                        {course.course_code}
                      </span>{' '}
                      {course.course_name}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground">{course.credits} credits</p>
                  </div>
                  {course.grade_letter && (
                    <div className="text-right">
                      <Badge tone={course.is_pass ? 'success' : 'danger'} className="text-sm">
                        {course.grade_letter}
                      </Badge>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {percent(course.percentage)} · GP {course.grade_point}
                      </p>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <THead>
                    <TR>
                      <TH>Component</TH>
                      <TH className="text-right">Obtained</TH>
                      <TH className="text-right">Maximum</TH>
                      <TH className="text-right">Weight</TH>
                      <TH>Remarks</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {course.components.map((component: any, index: number) => (
                      <TR key={index}>
                        <TD className="font-medium">{component.name}</TD>
                        <TD className="text-right tabular-nums">
                          {component.is_absent ? (
                            <Badge tone="danger">Absent</Badge>
                          ) : (
                            (component.marks_obtained ?? '—')
                          )}
                        </TD>
                        <TD className="text-right tabular-nums text-muted-foreground">
                          {component.max_marks}
                        </TD>
                        <TD className="text-right tabular-nums text-muted-foreground">
                          {component.weight}
                        </TD>
                        <TD className="max-w-[220px] truncate text-muted-foreground">
                          {component.remarks || '—'}
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
                {course.total_marks !== undefined && (
                  <p className="mt-3 text-sm text-muted-foreground">
                    Total {course.total_marks} · {percent(course.percentage)}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {transcript.semesters.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Transcript</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {transcript.semesters.map((semester) => (
              <div key={semester.semester_id}>
                <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="font-medium">
                    {semester.semester_name}{' '}
                    <span className="text-sm text-muted-foreground">({semester.session})</span>
                  </h3>
                  <p className="text-sm">
                    GPA <span className="font-semibold tabular-nums">{semester.gpa.toFixed(2)}</span>{' '}
                    · {semester.total_credits} credits
                  </p>
                </div>
                <Table>
                  <THead>
                    <TR>
                      <TH>Course</TH>
                      <TH className="text-right">Credits</TH>
                      <TH className="text-right">Marks</TH>
                      <TH className="text-right">Percentage</TH>
                      <TH>Grade</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {semester.courses.map((course) => (
                      <TR key={course.course_code}>
                        <TD>
                          <span className="font-mono text-xs text-muted-foreground">
                            {course.course_code}
                          </span>{' '}
                          {course.course_name}
                        </TD>
                        <TD className="text-right tabular-nums">{course.credits}</TD>
                        <TD className="text-right tabular-nums">{course.total_marks}</TD>
                        <TD className="text-right tabular-nums">{percent(course.percentage)}</TD>
                        <TD>
                          <Badge tone={course.is_pass ? 'success' : 'danger'}>
                            {course.grade_letter}
                          </Badge>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
function FacultyGradebook() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [sectionId, setSectionId] = useState('');
  const [edits, setEdits] = useState<Record<string, string>>({});

  const sectionsQuery = useQuery({
    queryKey: ['my-courses'],
    queryFn: () => api.get<CourseSection[]>('/courses/my-courses'),
  });

  const sections = sectionsQuery.data ?? [];
  const activeSection = sectionId || sections[0]?.id || '';

  const gradebookQuery = useQuery({
    queryKey: ['gradebook', activeSection],
    queryFn: () => api.get<GradebookGrid>(`/gradebook/section/${activeSection}`),
    enabled: Boolean(activeSection),
  });

  useEffect(() => setEdits({}), [activeSection]);

  const saveMarks = useMutation({
    mutationFn: async (componentId: string) => {
      const scores = Object.entries(edits)
        .filter(([key]) => key.startsWith(`${componentId}:`))
        .map(([key, value]) => ({
          student: key.split(':')[1],
          marks_obtained: value === '' ? null : Number(value),
        }));
      if (scores.length === 0) throw new ApiError(400, { code: 'noop', message: 'Nothing to save.' });
      return api.post<{ updated: number; rejected: any[] }>('/scores/bulk', {
        component: componentId,
        scores,
      });
    },
    onSuccess: (result) => {
      if (result.rejected?.length) {
        toast.warning(`${result.updated} saved, ${result.rejected.length} rejected`, {
          description: result.rejected[0]?.reason,
        });
      } else {
        toast.success(`${result.updated} marks saved`);
      }
      setEdits({});
      queryClient.invalidateQueries({ queryKey: ['gradebook', activeSection] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Marks could not be saved.'),
  });

  const publish = useMutation({
    mutationFn: (componentId: string) => api.post('/scores/publish', { component: componentId }),
    onSuccess: (result: any) => {
      toast.success(`Published ${result.published} marks for ${result.component}`);
      queryClient.invalidateQueries({ queryKey: ['gradebook', activeSection] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Marks could not be published.'),
  });

  if (sectionsQuery.isLoading) return <LoadingState rows={4} />;
  if (sections.length === 0) {
    return <EmptyState title="No sections assigned" description="You teach no sections yet." />;
  }

  const grid = gradebookQuery.data;
  const pendingComponents = new Set(
    Object.keys(edits).map((key) => key.split(':')[0]),
  );

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
        <Button
          variant="outline"
          onClick={() =>
            downloadFile(
              `/exports/gradebook/${activeSection}`,
              `gradebook-${grid?.section.course_code ?? 'section'}.csv`,
            ).catch((error) =>
              toast.error(error instanceof ApiError ? error.message : 'Export failed.'),
            )
          }
        >
          <Download className="h-4 w-4" aria-hidden />
          Export CSV
        </Button>
      </div>

      {gradebookQuery.isLoading && <LoadingState rows={4} />}
      {gradebookQuery.error && (
        <ErrorState
          message="The gradebook could not be loaded."
          onRetry={() => gradebookQuery.refetch()}
        />
      )}

      {grid && (
        <>
          {grid.components.length === 0 ? (
            <EmptyState
              title="No assessment components"
              description="Add components for this section before entering marks."
            />
          ) : (
            <>
              <Alert tone="default">
                Marks are scaled onto each component&apos;s configured weight. Publishing locks them —
                a correction then needs the publish permission and is written to the audit log.
              </Alert>

              <div className="flex flex-wrap gap-2">
                {grid.components.map((component) => (
                  <div
                    key={component.id}
                    className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2"
                  >
                    <span className="text-sm font-medium">{component.name}</span>
                    <span className="text-xs text-muted-foreground">
                      /{component.max_marks} → {component.weight}
                    </span>
                    {pendingComponents.has(component.id) && (
                      <Button
                        size="sm"
                        loading={saveMarks.isPending}
                        onClick={() => saveMarks.mutate(component.id)}
                      >
                        Save
                      </Button>
                    )}
                    {can('marks.publish') && (
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={publish.isPending}
                        onClick={() => publish.mutate(component.id)}
                        title="Publish and lock this component"
                      >
                        <Send className="h-3.5 w-3.5" aria-hidden />
                      </Button>
                    )}
                  </div>
                ))}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>
                    {grid.section.course_code} — Section {grid.section.name}
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {grid.students.length} students · internal total out of {grid.internal_max}
                  </p>
                </CardHeader>
                <CardContent>
                  <Table>
                    <THead>
                      <TR>
                        <TH className="sticky left-0 z-10 bg-muted/60">Student</TH>
                        {grid.components.map((component) => (
                          <TH key={component.id} className="text-right">
                            {component.name}
                            <span className="block font-normal normal-case text-muted-foreground">
                              /{component.max_marks}
                            </span>
                          </TH>
                        ))}
                        <TH className="text-right">Internal</TH>
                        <TH className="text-right">Total</TH>
                        <TH className="text-right">%</TH>
                        <TH>Grade</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {grid.students.map((student) => (
                        <TR key={student.student_id}>
                          <TD className="sticky left-0 z-10 bg-card">
                            <p className="max-w-[180px] truncate font-medium">
                              {student.full_name}
                            </p>
                            <p className="font-mono text-xs text-muted-foreground">
                              {student.enrollment_number}
                            </p>
                          </TD>
                          {student.cells.map((cell) => {
                            const key = `${cell.component_id}:${student.student_id}`;
                            const value =
                              edits[key] ??
                              (cell.marks_obtained !== null ? String(cell.marks_obtained) : '');
                            return (
                              <TD key={cell.component_id} className="text-right">
                                {cell.is_locked ? (
                                  <span className="inline-flex items-center gap-1 tabular-nums">
                                    {cell.marks_obtained ?? '—'}
                                    <Lock
                                      className="h-3 w-3 text-muted-foreground"
                                      aria-label="Published and locked"
                                    />
                                  </span>
                                ) : (
                                  <Input
                                    type="number"
                                    min={0}
                                    step="0.5"
                                    value={value}
                                    onChange={(event) =>
                                      setEdits((previous) => ({
                                        ...previous,
                                        [key]: event.target.value,
                                      }))
                                    }
                                    aria-label={`Marks for ${student.full_name}`}
                                    className="h-8 w-20 text-right tabular-nums"
                                  />
                                )}
                              </TD>
                            );
                          })}
                          <TD className="text-right tabular-nums">{student.internal_total}</TD>
                          <TD className="text-right font-medium tabular-nums">
                            {student.total_marks}
                          </TD>
                          <TD className="text-right tabular-nums">{percent(student.percentage)}</TD>
                          <TD>
                            {student.grade_letter && (
                              <Badge tone={student.is_pass ? 'success' : 'danger'}>
                                {student.grade_letter}
                              </Badge>
                            )}
                          </TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}
