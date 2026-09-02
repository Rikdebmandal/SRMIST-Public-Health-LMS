'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  Field,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  Select,
  StatCard,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { Department } from '@/types';

export default function AdminAcademicsPage() {
  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: 'Administration' }, { label: 'Academic setup' }]}
        title="Academic structure"
        description="Departments, programs, sessions, semesters, batches and curriculum."
      />

      <Tabs defaultValue="departments">
        <TabsList>
          <TabsTrigger value="departments">Departments</TabsTrigger>
          <TabsTrigger value="programs">Programs</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="curriculum">Curriculum</TabsTrigger>
        </TabsList>

        <TabsContent value="departments">
          <DepartmentsTab />
        </TabsContent>
        <TabsContent value="programs">
          <ProgramsTab />
        </TabsContent>
        <TabsContent value="sessions">
          <SessionsTab />
        </TabsContent>
        <TabsContent value="curriculum">
          <CurriculumTab />
        </TabsContent>
      </Tabs>
    </>
  );
}

function DepartmentsTab() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', code: '', description: '' });

  const { data, isLoading } = useQuery({
    queryKey: ['departments'],
    queryFn: () => api.get<Paginated<Department>>('/departments'),
  });

  const create = useMutation({
    mutationFn: () => api.post('/departments', form),
    onSuccess: () => {
      toast.success('Department created');
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      setCreating(false);
      setForm({ name: '', code: '', description: '' });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The department could not be created.');
      }
    },
  });

  if (isLoading) return <LoadingState rows={3} />;
  const departments = toList(data);

  return (
    <>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden />
          New department
        </Button>
      </div>

      {departments.length === 0 ? (
        <EmptyState title="No departments" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {departments.map((department) => (
            <Card key={department.id} className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">{department.name}</p>
                  <p className="font-mono text-xs text-muted-foreground">{department.code}</p>
                </div>
                <Badge tone={department.is_active ? 'success' : 'muted'}>
                  {department.is_active ? 'active' : 'inactive'}
                </Badge>
              </div>
              {department.description && (
                <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                  {department.description}
                </p>
              )}
              <div className="mt-3 flex gap-4 border-t border-border pt-3 text-xs text-muted-foreground">
                <span>{department.program_count} programs</span>
                <span>{department.member_count} members</span>
              </div>
              {department.hod_name && (
                <p className="mt-2 text-xs text-muted-foreground">Head: {department.hod_name}</p>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="New department"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button
              loading={create.isPending}
              disabled={!form.name.trim() || !form.code.trim()}
              onClick={() => create.mutate()}
            >
              Create
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Name" required>
            {(props) => (
              <Input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                {...props}
              />
            )}
          </Field>
          <Field label="Code" required hint="Short unique code, e.g. BIO.">
            {(props) => (
              <Input
                value={form.code}
                onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
                {...props}
              />
            )}
          </Field>
          <Field label="Description">
            {(props) => (
              <Input
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                {...props}
              />
            )}
          </Field>
        </div>
      </Modal>
    </>
  );
}

function ProgramsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['programs'],
    queryFn: () => api.get<Paginated<any>>('/programs'),
  });

  if (isLoading) return <LoadingState rows={3} />;
  const programs = toList(data);

  return programs.length === 0 ? (
    <EmptyState title="No programs configured" />
  ) : (
    <Table>
      <THead>
        <TR>
          <TH>Program</TH>
          <TH>Code</TH>
          <TH>Department</TH>
          <TH>Level</TH>
          <TH className="text-right">Semesters</TH>
          <TH className="text-right">Credits</TH>
          <TH className="text-right">Students</TH>
        </TR>
      </THead>
      <TBody>
        {programs.map((program: any) => (
          <TR key={program.id}>
            <TD className="font-medium">{program.name}</TD>
            <TD className="font-mono text-xs">{program.code}</TD>
            <TD className="text-muted-foreground">{program.department_name}</TD>
            <TD>
              <Badge tone="muted">{program.level_display}</Badge>
            </TD>
            <TD className="text-right tabular-nums">{program.total_semesters}</TD>
            <TD className="text-right tabular-nums">{program.total_credits}</TD>
            <TD className="text-right tabular-nums">{program.student_count}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}

function SessionsTab() {
  const sessionsQuery = useQuery({
    queryKey: ['academic-sessions'],
    queryFn: () => api.get<Paginated<any>>('/academic-sessions'),
  });

  const semestersQuery = useQuery({
    queryKey: ['semesters'],
    queryFn: () => api.get<Paginated<any>>('/semesters'),
  });

  if (sessionsQuery.isLoading) return <LoadingState rows={3} />;

  const sessions = toList(sessionsQuery.data);
  const semesters = toList(semestersQuery.data);

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Sessions" value={sessions.length} />
        <StatCard label="Semesters" value={semesters.length} />
        <StatCard
          label="Current session"
          value={sessions.find((session: any) => session.is_current)?.name ?? '—'}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Academic sessions</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Session</TH>
                <TH>Starts</TH>
                <TH>Ends</TH>
                <TH className="text-right">Semesters</TH>
                <TH>Status</TH>
              </TR>
            </THead>
            <TBody>
              {sessions.map((session: any) => (
                <TR key={session.id}>
                  <TD className="font-medium">{session.name}</TD>
                  <TD>{formatDate(session.start_date)}</TD>
                  <TD>{formatDate(session.end_date)}</TD>
                  <TD className="text-right tabular-nums">{session.semester_count}</TD>
                  <TD>
                    {session.is_current ? (
                      <Badge tone="success">current</Badge>
                    ) : (
                      <Badge tone="muted">archived</Badge>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Semesters</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Semester</TH>
                <TH>Session</TH>
                <TH>Teaching period</TH>
                <TH>Examinations</TH>
                <TH>Status</TH>
              </TR>
            </THead>
            <TBody>
              {semesters.map((semester: any) => (
                <TR key={semester.id}>
                  <TD className="font-medium">{semester.name}</TD>
                  <TD className="text-muted-foreground">{semester.session_name}</TD>
                  <TD className="whitespace-nowrap text-sm">
                    {formatDate(semester.start_date)} – {formatDate(semester.end_date)}
                  </TD>
                  <TD className="whitespace-nowrap text-sm text-muted-foreground">
                    {semester.exam_start_date
                      ? `${formatDate(semester.exam_start_date)} – ${formatDate(semester.exam_end_date)}`
                      : '—'}
                  </TD>
                  <TD>
                    {semester.is_current ? (
                      <Badge tone="success">current</Badge>
                    ) : (
                      <Badge tone="muted">—</Badge>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function CurriculumTab() {
  const [programId, setProgramId] = useState('');

  const programsQuery = useQuery({
    queryKey: ['programs'],
    queryFn: () => api.get<Paginated<any>>('/programs'),
  });

  const programs = toList(programsQuery.data);
  const active = programId || programs[0]?.id || '';

  const curriculumQuery = useQuery({
    queryKey: ['curriculum', active],
    queryFn: () => api.get<any>(`/curriculum/by-program?program=${active}`),
    enabled: Boolean(active),
  });

  if (programsQuery.isLoading) return <LoadingState rows={3} />;

  return (
    <div className="space-y-5">
      <Select
        value={active}
        onChange={(event) => setProgramId(event.target.value)}
        aria-label="Select a program"
        className="sm:max-w-sm"
      >
        {programs.map((program: any) => (
          <option key={program.id} value={program.id}>
            {program.name}
          </option>
        ))}
      </Select>

      {curriculumQuery.isLoading && <LoadingState rows={3} />}
      {curriculumQuery.data?.semesters?.length === 0 && (
        <EmptyState title="No curriculum defined for this program" />
      )}

      {curriculumQuery.data?.semesters?.map((semester: any) => (
        <Card key={semester.semester_number}>
          <CardHeader>
            <div className="flex items-baseline justify-between gap-2">
              <CardTitle>Semester {semester.semester_number}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {semester.total_credits} credits · {semester.courses.length} courses
              </p>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Code</TH>
                  <TH>Course</TH>
                  <TH>Category</TH>
                  <TH className="text-right">Credits</TH>
                  <TH>Mandatory</TH>
                </TR>
              </THead>
              <TBody>
                {semester.courses.map((item: any) => (
                  <TR key={item.id}>
                    <TD className="font-mono text-xs">{item.course_code}</TD>
                    <TD className="font-medium">{item.course_name}</TD>
                    <TD>
                      <Badge tone="muted">{item.category_display}</Badge>
                    </TD>
                    <TD className="text-right tabular-nums">{item.credits}</TD>
                    <TD>{item.is_mandatory ? 'Yes' : 'Elective'}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
