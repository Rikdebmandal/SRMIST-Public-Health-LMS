'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
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
  ErrorState,
  LoadingState,
  PageHeader,
  Select,
} from '@/components/ui';
import { ApiError, api } from '@/lib/api';

interface Catalogue {
  permissions: { code: string; label: string; domain: string }[];
  roles: { code: string; label: string }[];
  matrix: Record<string, string[]>;
}

export default function AdminRolesPage() {
  const queryClient = useQueryClient();
  const [role, setRole] = useState('STUDENT');
  const [granted, setGranted] = useState<Set<string>>(new Set());

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['permission-catalogue'],
    queryFn: () => api.get<Catalogue>('/roles/permissions/catalogue'),
  });

  useEffect(() => {
    if (data) setGranted(new Set(data.matrix[role] ?? []));
  }, [data, role]);

  const save = useMutation({
    mutationFn: () =>
      api.post('/roles/permissions/bulk-set', { role, permissions: Array.from(granted) }),
    onSuccess: () => {
      toast.success('Role permissions updated');
      queryClient.invalidateQueries({ queryKey: ['permission-catalogue'] });
    },
    onError: (mutationError) =>
      toast.error(
        mutationError instanceof ApiError
          ? mutationError.message
          : 'Permissions could not be saved.',
      ),
  });

  if (isLoading) return <LoadingState rows={5} />;
  if (error || !data) {
    return <ErrorState message="The permission catalogue could not be loaded." onRetry={() => refetch()} />;
  }

  const domains = Array.from(new Set(data.permissions.map((permission) => permission.domain)));
  const original = new Set(data.matrix[role] ?? []);
  const dirty =
    granted.size !== original.size ||
    Array.from(granted).some((code) => !original.has(code));

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: 'Administration' }, { label: 'Roles' }]}
        title="Roles and permissions"
        description="The permission matrix the API enforces on every request."
        actions={
          <Button loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
            <ShieldCheck className="h-4 w-4" aria-hidden />
            Save changes
          </Button>
        }
      />

      <Alert tone="warning" className="mb-5" title="These changes take effect immediately">
        Removing a permission revokes it for every user holding this role. Server-side checks
        enforce the matrix — hiding a menu item alone never protects data.
      </Alert>

      <Card className="mb-5">
        <CardContent className="pt-4 sm:pt-5">
          <label className="mb-1.5 block text-sm font-medium" htmlFor="role-select">
            Editing role
          </label>
          <Select
            id="role-select"
            value={role}
            onChange={(event) => setRole(event.target.value)}
            className="sm:max-w-xs"
          >
            {data.roles.map((option) => (
              <option key={option.code} value={option.code}>
                {option.label}
              </option>
            ))}
          </Select>
          <p className="mt-2 text-sm text-muted-foreground">
            {granted.size} of {data.permissions.length} permissions granted
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {domains.map((domain) => (
          <Card key={domain}>
            <CardHeader>
              <CardTitle className="capitalize">{domain.replace('_', ' ')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.permissions
                .filter((permission) => permission.domain === domain)
                .map((permission) => (
                  <label
                    key={permission.code}
                    className="flex cursor-pointer items-start gap-2.5 rounded-md p-1.5 hover:bg-muted"
                  >
                    <input
                      type="checkbox"
                      checked={granted.has(permission.code)}
                      onChange={(event) => {
                        const next = new Set(granted);
                        if (event.target.checked) next.add(permission.code);
                        else next.delete(permission.code);
                        setGranted(next);
                      }}
                      className="mt-0.5 h-4 w-4 shrink-0 rounded border-input accent-[hsl(var(--primary))]"
                    />
                    <span className="min-w-0">
                      <span className="block text-sm">{permission.label}</span>
                      <span className="block font-mono text-[10px] text-muted-foreground">
                        {permission.code}
                      </span>
                    </span>
                  </label>
                ))}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-5">
        <CardHeader>
          <CardTitle>Current matrix</CardTitle>
          <p className="text-sm text-muted-foreground">Permission counts per role.</p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {data.roles.map((option) => (
              <Badge key={option.code} tone={option.code === role ? 'default' : 'muted'}>
                {option.label}: {(data.matrix[option.code] ?? []).length}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
