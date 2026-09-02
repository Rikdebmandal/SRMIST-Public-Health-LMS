'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Clock, FileUp, Plus, Upload } from 'lucide-react';
import { useState } from 'react';
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
  Field,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  Select,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate, relativeTime } from '@/lib/utils';
import type { Assignment, CourseSection } from '@/types';

export default function AssignmentsPage() {
  const { can } = useAuth();
  const isStaff = can('assignment.manage');
  const [creating, setCreating] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['assignments'],
    queryFn: () => api.get<Paginated<Assignment>>('/assignments?page_size=100'),
  });

  const assignments = toList(data);
  const now = Date.now();

  const open = assignments.filter(
    (item) => item.status === 'PUBLISHED' && new Date(item.due_date).getTime() >= now,
  );
  const past = assignments.filter(
    (item) => item.status !== 'PUBLISHED' || new Date(item.due_date).getTime() < now,
  );

  return (
    <>
      <PageHeader
        title="Assignments"
        description={
          isStaff
            ? 'Create work, track submissions and grade.'
            : 'Submit your work and track feedback.'
        }
        actions={
          isStaff && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              New assignment
            </Button>
          )
        }
      />

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Assignments could not be loaded." onRetry={() => refetch()} />}

      {!isLoading && !error && (
        <Tabs defaultValue="open">
          <TabsList>
            <TabsTrigger value="open">Open ({open.length})</TabsTrigger>
            <TabsTrigger value="past">Past &amp; drafts ({past.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="open">
            {open.length === 0 ? (
              <EmptyState
                title="Nothing open"
                description={
                  isStaff
                    ? 'Create an assignment to get started.'
                    : 'You have no assignments due right now.'
                }
              />
            ) : (
              <div className="space-y-3">
                {open.map((assignment) => (
                  <AssignmentCard key={assignment.id} assignment={assignment} isStaff={isStaff} />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="past">
            {past.length === 0 ? (
              <EmptyState title="Nothing here yet" />
            ) : (
              <div className="space-y-3">
                {past.map((assignment) => (
                  <AssignmentCard key={assignment.id} assignment={assignment} isStaff={isStaff} />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}

      {creating && <CreateAssignmentModal onClose={() => setCreating(false)} />}
    </>
  );
}

function AssignmentCard({ assignment, isStaff }: { assignment: Assignment; isStaff: boolean }) {
  const [submitting, setSubmitting] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const submission = assignment.my_submission;
  const overdue = new Date(assignment.due_date).getTime() < Date.now();

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">
                {assignment.course_code}
              </span>
              <Badge
                tone={
                  assignment.status === 'PUBLISHED'
                    ? overdue
                      ? 'muted'
                      : 'success'
                    : assignment.status === 'DRAFT'
                      ? 'warning'
                      : 'muted'
                }
              >
                {assignment.status.toLowerCase()}
              </Badge>
              {submission && (
                <Badge
                  tone={
                    submission.status === 'GRADED'
                      ? 'success'
                      : submission.is_late
                        ? 'warning'
                        : 'default'
                  }
                >
                  {submission.status.toLowerCase()}
                </Badge>
              )}
            </div>
            <h3 className="mt-1.5 font-medium">{assignment.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{assignment.description}</p>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" aria-hidden />
                Due {formatDate(assignment.due_date, true)} ({relativeTime(assignment.due_date)})
              </span>
              <span>{assignment.max_marks} marks</span>
              {assignment.allowed_extensions.length > 0 && (
                <span>{assignment.allowed_extensions.join(', ').toUpperCase()}</span>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-col gap-2 sm:items-end">
            {isStaff && assignment.submission_stats && (
              <div className="text-right text-sm">
                <p className="font-medium tabular-nums">
                  {assignment.submission_stats.submitted}/{assignment.submission_stats.enrolled}
                </p>
                <p className="text-xs text-muted-foreground">
                  submitted · {assignment.submission_stats.graded} graded
                </p>
              </div>
            )}
            {isStaff ? (
              <Button size="sm" variant="outline" onClick={() => setReviewing(true)}>
                Review submissions
              </Button>
            ) : (
              assignment.is_open && (
                <Button size="sm" onClick={() => setSubmitting(true)}>
                  <Upload className="h-3.5 w-3.5" aria-hidden />
                  {submission ? 'Replace submission' : 'Submit'}
                </Button>
              )
            )}
          </div>
        </div>

        {submission?.status === 'GRADED' && (
          <Alert tone="success" className="mt-3" title={`Graded: ${submission.marks_obtained}/${assignment.max_marks}`}>
            {submission.feedback || 'No written feedback was left.'}
          </Alert>
        )}
      </CardContent>

      {submitting && (
        <SubmitModal assignment={assignment} onClose={() => setSubmitting(false)} />
      )}
      {reviewing && (
        <SubmissionsModal assignment={assignment} onClose={() => setReviewing(false)} />
      )}
    </Card>
  );
}

function SubmitModal({ assignment, onClose }: { assignment: Assignment; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');

  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append('assignment', assignment.id);
      if (file) form.append('file', file);
      if (text) form.append('text_response', text);
      return api.post('/submissions', form);
    },
    onSuccess: () => {
      toast.success('Submission received');
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, {
          description: error.fieldMessages.join(' ') || undefined,
        });
      } else {
        toast.error('The submission could not be uploaded.');
      }
    },
  });

  const overdue = new Date(assignment.due_date).getTime() < Date.now();

  return (
    <Modal
      open
      onClose={onClose}
      title={assignment.title}
      description={`Due ${formatDate(assignment.due_date, true)} · ${assignment.max_marks} marks`}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={submit.isPending}
            disabled={!file && !text.trim()}
            onClick={() => submit.mutate()}
          >
            <FileUp className="h-4 w-4" aria-hidden />
            Submit
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {overdue && assignment.allow_late_submission && (
          <Alert tone="warning" title="This is a late submission">
            The deadline has passed. A {assignment.late_penalty_percent}% penalty may be applied.
          </Alert>
        )}
        {assignment.instructions && (
          <div className="rounded-md border border-border p-3 text-sm">
            <p className="mb-1 font-medium">Instructions</p>
            <p className="text-muted-foreground">{assignment.instructions}</p>
          </div>
        )}

        <Field
          label="Upload file"
          hint={`Allowed: ${
            assignment.allowed_extensions.join(', ').toUpperCase() || 'any permitted type'
          } · max ${assignment.max_file_size_mb} MB`}
        >
          {(props) => (
            <Input
              type="file"
              accept={assignment.allowed_extensions.map((ext) => `.${ext}`).join(',')}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              {...props}
            />
          )}
        </Field>

        <Field label="Written response" hint="Optional if you attach a file.">
          {(props) => (
            <Textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              rows={5}
              placeholder="Type your response…"
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}

function SubmissionsModal({
  assignment,
  onClose,
}: {
  assignment: Assignment;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [grades, setGrades] = useState<Record<string, { marks: string; feedback: string }>>({});

  const { data, isLoading } = useQuery({
    queryKey: ['submissions', assignment.id],
    queryFn: () => api.get<{ submissions: any[]; pending: any[] }>(
      `/assignments/${assignment.id}/submissions`,
    ),
  });

  const grade = useMutation({
    mutationFn: ({ id, marks, feedback }: { id: string; marks: number; feedback: string }) =>
      api.post(`/submissions/${id}/grade`, { marks_obtained: marks, feedback }),
    onSuccess: () => {
      toast.success('Grade saved');
      queryClient.invalidateQueries({ queryKey: ['submissions', assignment.id] });
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The grade could not be saved.'),
  });

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Submissions — ${assignment.title}`}
      description={`${assignment.course_code} · out of ${assignment.max_marks}`}
      footer={
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
      }
    >
      {isLoading ? (
        <LoadingState rows={4} />
      ) : (
        <div className="space-y-5">
          <div>
            <h3 className="mb-2 text-sm font-semibold">
              Submitted ({data?.submissions.length ?? 0})
            </h3>
            {data?.submissions.length === 0 ? (
              <EmptyState title="No submissions yet" />
            ) : (
              <ul className="divide-y divide-border">
                {data?.submissions.map((submission: any) => {
                  const draft = grades[submission.id] ?? {
                    marks: submission.marks_obtained ?? '',
                    feedback: submission.feedback ?? '',
                  };
                  return (
                    <li key={submission.id} className="py-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {submission.student_detail?.full_name}
                          </p>
                          <p className="font-mono text-xs text-muted-foreground">
                            {submission.enrollment_number} ·{' '}
                            {formatDate(submission.submitted_at, true)}
                          </p>
                        </div>
                        <Badge tone={submission.is_late ? 'warning' : 'success'}>
                          {submission.is_late ? 'late' : 'on time'}
                        </Badge>
                      </div>

                      {submission.text_response && (
                        <p className="mt-2 rounded-md bg-muted p-2 text-sm">
                          {submission.text_response}
                        </p>
                      )}
                      {submission.file && (
                        <a
                          href={submission.file}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
                        >
                          Open attachment
                        </a>
                      )}

                      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                        <Input
                          type="number"
                          min={0}
                          max={Number(assignment.max_marks)}
                          value={draft.marks}
                          onChange={(event) =>
                            setGrades((previous) => ({
                              ...previous,
                              [submission.id]: { ...draft, marks: event.target.value },
                            }))
                          }
                          aria-label={`Marks for ${submission.student_detail?.full_name}`}
                          placeholder={`/ ${assignment.max_marks}`}
                          className="sm:w-28"
                        />
                        <Input
                          value={draft.feedback}
                          onChange={(event) =>
                            setGrades((previous) => ({
                              ...previous,
                              [submission.id]: { ...draft, feedback: event.target.value },
                            }))
                          }
                          aria-label={`Feedback for ${submission.student_detail?.full_name}`}
                          placeholder="Feedback"
                          className="flex-1"
                        />
                        <Button
                          size="sm"
                          loading={grade.isPending}
                          disabled={draft.marks === ''}
                          onClick={() =>
                            grade.mutate({
                              id: submission.id,
                              marks: Number(draft.marks),
                              feedback: draft.feedback,
                            })
                          }
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                          Grade
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {data?.pending && data.pending.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">
                Not submitted ({data.pending.length})
              </h3>
              <ul className="flex flex-wrap gap-1.5">
                {data.pending.map((student: any) => (
                  <li key={student.student_id}>
                    <Badge tone="muted">
                      {student.full_name} · {student.enrollment_number}
                    </Badge>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function CreateAssignmentModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    section: '',
    title: '',
    description: '',
    instructions: '',
    max_marks: '20',
    due_date: '',
    allow_late_submission: true,
  });

  const sectionsQuery = useQuery({
    queryKey: ['my-courses'],
    queryFn: () => api.get<CourseSection[]>('/courses/my-courses'),
  });

  const create = useMutation({
    mutationFn: async () => {
      const created = await api.post<Assignment>('/assignments', {
        ...form,
        max_marks: Number(form.max_marks),
        due_date: new Date(form.due_date).toISOString(),
        allowed_extensions: ['pdf', 'docx'],
      });
      await api.post(`/assignments/${created.id}/publish`);
      return created;
    },
    onSuccess: () => {
      toast.success('Assignment published and students notified');
      queryClient.invalidateQueries({ queryKey: ['assignments'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The assignment could not be created.');
      }
    },
  });

  const sections = sectionsQuery.data ?? [];
  const valid = form.section && form.title.trim() && form.due_date;

  return (
    <Modal
      open
      onClose={onClose}
      title="New assignment"
      description="Publishing sends an in-app notification to every enrolled student."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={create.isPending} disabled={!valid} onClick={() => create.mutate()}>
            Publish
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Section" required>
          {(props) => (
            <Select
              value={form.section}
              onChange={(event) => setForm({ ...form, section: event.target.value })}
              {...props}
            >
              <option value="">Choose a section…</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.course_code} — Sec {section.name}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Title" required>
          {(props) => (
            <Input
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder="e.g. Assignment 3: Survival analysis"
              {...props}
            />
          )}
        </Field>

        <Field label="Description">
          {(props) => (
            <Textarea
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              rows={3}
              {...props}
            />
          )}
        </Field>

        <Field label="Instructions">
          {(props) => (
            <Textarea
              value={form.instructions}
              onChange={(event) => setForm({ ...form, instructions: event.target.value })}
              rows={3}
              placeholder="Submission format, citation requirements…"
              {...props}
            />
          )}
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Maximum marks" required>
            {(props) => (
              <Input
                type="number"
                min={1}
                value={form.max_marks}
                onChange={(event) => setForm({ ...form, max_marks: event.target.value })}
                {...props}
              />
            )}
          </Field>
          <Field label="Due date and time" required>
            {(props) => (
              <Input
                type="datetime-local"
                value={form.due_date}
                onChange={(event) => setForm({ ...form, due_date: event.target.value })}
                {...props}
              />
            )}
          </Field>
        </div>
      </div>
    </Modal>
  );
}
