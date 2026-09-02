'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, KeyRound, Plus, Search, UserCog } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import {
  Avatar,
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  Select,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
} from '@/components/ui';
import { ApiError, api, downloadFile, toList, type Paginated } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { Department, Role, User } from '@/types';

const ROLES: { value: Role; label: string }[] = [
  { value: 'STUDENT', label: 'Student' },
  { value: 'FACULTY', label: 'Faculty' },
  { value: 'SCHOLAR', label: 'Research scholar' },
  { value: 'ADMIN', label: 'HOD / Staff admin' },
  { value: 'DEAN', label: 'Dean' },
  { value: 'ALUMNI', label: 'Alumni' },
];

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [term, setTerm] = useState('');
  const [role, setRole] = useState('');
  const [creating, setCreating] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-users', role],
    queryFn: () =>
      api.get<Paginated<User>>(`/users?page_size=100${role ? `&role=${role}` : ''}`),
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.post(`/users/${id}/${active ? 'deactivate' : 'activate'}`),
    onSuccess: () => {
      toast.success('Account status updated');
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The account could not be updated.'),
  });

  const resetPassword = useMutation({
    mutationFn: (id: string) =>
      api.post<{ temporary_password: string }>(`/users/${id}/reset-password`),
    onSuccess: (result) => {
      toast.success('Temporary password generated', {
        description: `Share securely: ${result.temporary_password}`,
        duration: 15_000,
      });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The password could not be reset.'),
  });

  const users = toList(data).filter(
    (user) =>
      !term ||
      user.full_name.toLowerCase().includes(term.toLowerCase()) ||
      user.email.toLowerCase().includes(term.toLowerCase()),
  );

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: 'Administration' }, { label: 'Users' }]}
        title="User management"
        description="Create accounts, assign roles and manage access."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() =>
                downloadFile('/exports/students', 'students.csv').catch((exportError) =>
                  toast.error(
                    exportError instanceof ApiError ? exportError.message : 'Export failed.',
                  ),
                )
              }
            >
              <Download className="h-4 w-4" aria-hidden />
              Export students
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              New user
            </Button>
          </>
        }
      />

      <Card className="mb-5">
        <CardContent className="flex flex-col gap-2 pt-4 sm:flex-row sm:pt-5">
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search by name or email"
              aria-label="Search users"
              className="pl-9"
            />
          </div>
          <Select
            value={role}
            onChange={(event) => setRole(event.target.value)}
            aria-label="Filter by role"
            className="sm:w-48"
          >
            <option value="">All roles</option>
            {ROLES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>

      {isLoading && <LoadingState rows={4} />}
      {error && <ErrorState message="Users could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && users.length === 0 && <EmptyState title="No users match" />}

      {users.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>User</TH>
              <TH>Role</TH>
              <TH>Department</TH>
              <TH>Identifier</TH>
              <TH>Status</TH>
              <TH>Last active</TH>
              <TH className="text-right">Actions</TH>
            </TR>
          </THead>
          <TBody>
            {users.map((user) => {
              const profile = user.profile as any;
              const identifier =
                profile?.enrollment_number ??
                profile?.employee_id ??
                profile?.registration_number ??
                '—';
              return (
                <TR key={user.id}>
                  <TD>
                    <div className="flex items-center gap-2.5">
                      <Avatar name={user.full_name} src={user.avatar} size="sm" />
                      <div className="min-w-0">
                        <p className="max-w-[180px] truncate font-medium">{user.full_name}</p>
                        <p className="max-w-[180px] truncate text-xs text-muted-foreground">
                          {user.email}
                        </p>
                      </div>
                    </div>
                  </TD>
                  <TD>
                    <Badge tone="muted">{user.role_display}</Badge>
                  </TD>
                  <TD className="text-muted-foreground">{user.department_code || '—'}</TD>
                  <TD className="font-mono text-xs">{identifier}</TD>
                  <TD>
                    <Badge tone={user.is_active ? 'success' : 'danger'}>
                      {user.is_active ? 'active' : 'disabled'}
                    </Badge>
                  </TD>
                  <TD className="whitespace-nowrap text-xs text-muted-foreground">
                    {user.last_active_at ? formatDate(user.last_active_at) : '—'}
                  </TD>
                  <TD className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        title="Reset password"
                        onClick={() => resetPassword.mutate(user.id)}
                      >
                        <KeyRound className="h-3.5 w-3.5" aria-hidden />
                        <span className="sr-only">Reset password for {user.full_name}</span>
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          toggleActive.mutate({ id: user.id, active: user.is_active })
                        }
                      >
                        {user.is_active ? 'Disable' : 'Enable'}
                      </Button>
                    </div>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}

      {creating && <CreateUserModal onClose={() => setCreating(false)} />}
    </>
  );
}

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    role: 'STUDENT' as Role,
    department: '',
    password: '',
    enrollment_number: '',
    employee_id: '',
  });

  const departmentsQuery = useQuery({
    queryKey: ['departments'],
    queryFn: () => api.get<Paginated<Department>>('/departments'),
  });

  const create = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        full_name: form.full_name,
        email: form.email,
        role: form.role,
        department: form.department || null,
        password: form.password || undefined,
        must_change_password: true,
      };
      if (form.role === 'STUDENT') {
        payload.student_profile = { enrollment_number: form.enrollment_number };
      }
      if (['FACULTY', 'ADMIN', 'DEAN'].includes(form.role)) {
        payload.faculty_profile = { employee_id: form.employee_id };
      }
      return api.post('/users', payload);
    },
    onSuccess: () => {
      toast.success('User created');
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The user could not be created.');
      }
    },
  });

  const needsEnrolment = form.role === 'STUDENT';
  const needsEmployeeId = ['FACULTY', 'ADMIN', 'DEAN'].includes(form.role);
  const valid =
    form.full_name.trim() &&
    form.email.trim() &&
    (!needsEnrolment || form.enrollment_number.trim()) &&
    (!needsEmployeeId || form.employee_id.trim());

  return (
    <Modal
      open
      onClose={onClose}
      title="Create a user"
      description="The account is created with a temporary password the user must change."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={create.isPending} disabled={!valid} onClick={() => create.mutate()}>
            <UserCog className="h-4 w-4" aria-hidden />
            Create user
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Full name" required>
          {(props) => (
            <Input
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <Field label="Email" required>
          {(props) => (
            <Input
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Role" required>
            {(props) => (
              <Select
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value as Role })}
                {...props}
              >
                {ROLES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Department">
            {(props) => (
              <Select
                value={form.department}
                onChange={(event) => setForm({ ...form, department: event.target.value })}
                {...props}
              >
                <option value="">None</option>
                {toList(departmentsQuery.data).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>

        {needsEnrolment && (
          <Field label="Enrolment number" required>
            {(props) => (
              <Input
                value={form.enrollment_number}
                onChange={(event) =>
                  setForm({ ...form, enrollment_number: event.target.value })
                }
                placeholder="RA26HDS001"
                {...props}
              />
            )}
          </Field>
        )}

        {needsEmployeeId && (
          <Field label="Employee id" required>
            {(props) => (
              <Input
                value={form.employee_id}
                onChange={(event) => setForm({ ...form, employee_id: event.target.value })}
                placeholder="SPH-F005"
                {...props}
              />
            )}
          </Field>
        )}

        <Field
          label="Initial password"
          hint="Leave blank to generate one automatically. The user must change it at first sign-in."
        >
          {(props) => (
            <Input
              type="text"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}
