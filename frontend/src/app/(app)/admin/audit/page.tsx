'use client';

import { useQuery } from '@tanstack/react-query';
import { Search, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { CategoryBarChart } from '@/components/charts';
import {
  Alert,
  Badge,
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
import { api, toList, type Paginated } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { AuditLog } from '@/types';

const HIGH_RISK = new Set([
  'ROLE_CHANGE',
  'MARKS_CHANGE',
  'MARKS_PUBLISH',
  'ATTENDANCE_CHANGE',
  'PERMISSION_DENIED',
  'SETTINGS_CHANGE',
  'FILE_DELETE',
]);

export default function AdminAuditPage() {
  const [action, setAction] = useState('');
  const [term, setTerm] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['audit-logs', action],
    queryFn: () =>
      api.get<Paginated<AuditLog>>(
        `/audit-logs?page_size=100${action ? `&action=${action}` : ''}`,
      ),
  });

  const actionsQuery = useQuery({
    queryKey: ['audit-actions'],
    queryFn: () => api.get<{ code: string; label: string }[]>('/audit-logs/actions'),
  });

  const summaryQuery = useQuery({
    queryKey: ['audit-summary'],
    queryFn: () => api.get<any>('/audit-logs/summary'),
  });

  const logs = toList(data).filter(
    (log) =>
      !term ||
      log.actor_email.toLowerCase().includes(term.toLowerCase()) ||
      log.object_label.toLowerCase().includes(term.toLowerCase()) ||
      log.description.toLowerCase().includes(term.toLowerCase()),
  );

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: 'Administration' }, { label: 'Audit log' }]}
        title="Audit log"
        description="Append-only record of security-sensitive actions."
      />

      <Alert tone="default" className="mb-5" title="Immutable by design">
        Entries cannot be edited or deleted through the application — the model refuses both.
        Credentials and tokens are stripped before anything is written.
      </Alert>

      {summaryQuery.data && (
        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          <StatCard label="Total entries" value={summaryQuery.data.total} icon={ShieldCheck} />
          <StatCard
            label="Most frequent action"
            value={summaryQuery.data.by_action?.[0]?.action?.toLowerCase() ?? '—'}
            hint={`${summaryQuery.data.by_action?.[0]?.count ?? 0} entries`}
          />
          <StatCard label="Distinct actions" value={summaryQuery.data.by_action?.length ?? 0} />
        </div>
      )}

      {summaryQuery.data?.by_action?.length > 0 && (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>Actions recorded</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryBarChart
              data={summaryQuery.data.by_action.slice(0, 10).map((row: any) => ({
                label: row.action.replace('_', ' ').toLowerCase(),
                count: row.count,
              }))}
              xKey="label"
              yKey="count"
              label="Entries"
              unit=""
              domain={[0, Math.max(...summaryQuery.data.by_action.map((r: any) => r.count)) + 5]}
              height={220}
            />
          </CardContent>
        </Card>
      )}

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
              placeholder="Search actor, object or description"
              aria-label="Search audit log"
              className="pl-9"
            />
          </div>
          <Select
            value={action}
            onChange={(event) => setAction(event.target.value)}
            aria-label="Filter by action"
            className="sm:w-56"
          >
            <option value="">All actions</option>
            {(actionsQuery.data ?? []).map((option) => (
              <option key={option.code} value={option.code}>
                {option.label}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>

      {isLoading && <LoadingState rows={5} />}
      {error && <ErrorState message="The audit log could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && logs.length === 0 && <EmptyState title="No entries match" />}

      {logs.length > 0 && (
        <Table>
          <THead>
            <TR>
              <TH>When</TH>
              <TH>Actor</TH>
              <TH>Action</TH>
              <TH>Object</TH>
              <TH>Description</TH>
              <TH>IP</TH>
            </TR>
          </THead>
          <TBody>
            {logs.map((log) => (
              <TR key={log.id}>
                <TD className="whitespace-nowrap text-xs text-muted-foreground">
                  {formatDate(log.created_at, true)}
                </TD>
                <TD>
                  <p className="max-w-[180px] truncate text-sm">
                    {log.actor_email || 'system'}
                  </p>
                  {log.actor_role && (
                    <p className="text-xs text-muted-foreground">{log.actor_role}</p>
                  )}
                </TD>
                <TD>
                  <Badge tone={HIGH_RISK.has(log.action) ? 'warning' : 'muted'}>
                    {log.action_display}
                  </Badge>
                </TD>
                <TD className="max-w-[200px] truncate text-sm">{log.object_label || '—'}</TD>
                <TD className="max-w-[280px] truncate text-sm text-muted-foreground">
                  {log.description || '—'}
                </TD>
                <TD className="font-mono text-xs text-muted-foreground">
                  {log.ip_address || '—'}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
    </>
  );
}
