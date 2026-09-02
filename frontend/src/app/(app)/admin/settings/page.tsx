'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save } from 'lucide-react';
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
  Input,
  LoadingState,
  PageHeader,
  Select,
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
import { ApiError, api, toList } from '@/lib/api';
import type { SystemSetting } from '@/types';

const GROUP_LABELS: Record<string, string> = {
  BRANDING: 'Branding',
  ACADEMIC: 'Academic rules',
  NOTIFICATION: 'Notifications',
  SECURITY: 'Security',
  UPLOAD: 'Uploads',
  GENERAL: 'General',
};

export default function AdminSettingsPage() {
  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: 'Administration' }, { label: 'Configuration' }]}
        title="System configuration"
        description="Branding, academic rules, attendance thresholds and grading — all database-driven."
      />

      <Tabs defaultValue="settings">
        <TabsList>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="attendance">Attendance policy</TabsTrigger>
          <TabsTrigger value="grading">Grading scale</TabsTrigger>
          <TabsTrigger value="risk">Risk rules</TabsTrigger>
        </TabsList>

        <TabsContent value="settings">
          <SettingsTab />
        </TabsContent>
        <TabsContent value="attendance">
          <AttendancePolicyTab />
        </TabsContent>
        <TabsContent value="grading">
          <GradingTab />
        </TabsContent>
        <TabsContent value="risk">
          <RiskRulesTab />
        </TabsContent>
      </Tabs>
    </>
  );
}

function SettingsTab() {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>({});

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['system-settings'],
    queryFn: () => api.get<SystemSetting[]>('/settings'),
  });

  useEffect(() => {
    if (data) {
      const map: Record<string, string> = {};
      toList(data).forEach((setting) => {
        map[setting.key] = setting.value;
      });
      setValues(map);
    }
  }, [data]);

  const save = useMutation({
    mutationFn: () =>
      api.put('/settings/bulk', {
        settings: Object.entries(values).map(([key, value]) => ({ key, value })),
      }),
    onSuccess: () => {
      toast.success('Settings saved — reload to see branding changes');
      queryClient.invalidateQueries({ queryKey: ['system-settings'] });
    },
    onError: (mutationError) =>
      toast.error(
        mutationError instanceof ApiError ? mutationError.message : 'Settings could not be saved.',
      ),
  });

  if (isLoading) return <LoadingState rows={5} />;
  if (error) return <ErrorState message="Settings could not be loaded." onRetry={() => refetch()} />;

  const settings = toList(data);
  const groups = Array.from(new Set(settings.map((setting) => setting.group)));

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <Button loading={save.isPending} onClick={() => save.mutate()}>
          <Save className="h-4 w-4" aria-hidden />
          Save all settings
        </Button>
      </div>

      {groups.map((group) => (
        <Card key={group}>
          <CardHeader>
            <CardTitle>{GROUP_LABELS[group] ?? group}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {settings
              .filter((setting) => setting.group === group)
              .map((setting) => (
                <div key={setting.id} className="grid gap-2 sm:grid-cols-3 sm:items-start">
                  <div className="sm:col-span-1">
                    <label
                      htmlFor={`setting-${setting.key}`}
                      className="text-sm font-medium"
                    >
                      {setting.label}
                    </label>
                    <p className="font-mono text-[10px] text-muted-foreground">{setting.key}</p>
                    {setting.is_public && (
                      <Badge tone="muted" className="mt-1">
                        public
                      </Badge>
                    )}
                  </div>
                  <div className="sm:col-span-2">
                    {setting.value_type === 'BOOLEAN' ? (
                      <Select
                        id={`setting-${setting.key}`}
                        value={values[setting.key] ?? ''}
                        disabled={!setting.is_editable}
                        onChange={(event) =>
                          setValues({ ...values, [setting.key]: event.target.value })
                        }
                      >
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                      </Select>
                    ) : (
                      <Input
                        id={`setting-${setting.key}`}
                        type={
                          setting.value_type === 'NUMBER'
                            ? 'number'
                            : setting.value_type === 'COLOR'
                              ? 'text'
                              : 'text'
                        }
                        value={values[setting.key] ?? ''}
                        disabled={!setting.is_editable}
                        onChange={(event) =>
                          setValues({ ...values, [setting.key]: event.target.value })
                        }
                      />
                    )}
                    {setting.description && (
                      <p className="mt-1 text-xs text-muted-foreground">{setting.description}</p>
                    )}
                  </div>
                </div>
              ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function AttendancePolicyTab() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['attendance-policies'],
    queryFn: () => api.get<any[]>('/attendance/policies'),
  });

  const [edits, setEdits] = useState<Record<string, any>>({});

  const save = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) =>
      api.patch(`/attendance/policies/${id}`, payload),
    onSuccess: () => {
      toast.success('Attendance policy updated');
      queryClient.invalidateQueries({ queryKey: ['attendance-policies'] });
      setEdits({});
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The policy could not be saved.'),
  });

  if (isLoading) return <LoadingState rows={3} />;
  const policies = toList(data);

  return (
    <div className="space-y-4">
      <Alert tone="default" title="Thresholds are data, not code">
        The 75% requirement lives here. Changing it immediately affects every attendance
        calculation, warning and alert.
      </Alert>

      {policies.map((policy: any) => {
        const draft = edits[policy.id] ?? policy;
        return (
          <Card key={policy.id}>
            <CardHeader>
              <CardTitle>{policy.name}</CardTitle>
              <p className="text-sm text-muted-foreground">
                Scope: {policy.department_name || 'Institution-wide'}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Warning below (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={draft.warning_threshold}
                    onChange={(event) =>
                      setEdits({
                        ...edits,
                        [policy.id]: { ...draft, warning_threshold: event.target.value },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">Critical below (%)</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={draft.critical_threshold}
                    onChange={(event) =>
                      setEdits({
                        ...edits,
                        [policy.id]: { ...draft, critical_threshold: event.target.value },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Consecutive absence alert
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={draft.consecutive_absence_alert}
                    onChange={(event) =>
                      setEdits({
                        ...edits,
                        [policy.id]: {
                          ...draft,
                          consecutive_absence_alert: event.target.value,
                        },
                      })
                    }
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={draft.count_late_as_present}
                    onChange={(event) =>
                      setEdits({
                        ...edits,
                        [policy.id]: { ...draft, count_late_as_present: event.target.checked },
                      })
                    }
                    className="h-4 w-4 rounded border-input accent-[hsl(var(--primary))]"
                  />
                  Count late as present
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={draft.exclude_excused_from_total}
                    onChange={(event) =>
                      setEdits({
                        ...edits,
                        [policy.id]: {
                          ...draft,
                          exclude_excused_from_total: event.target.checked,
                        },
                      })
                    }
                    className="h-4 w-4 rounded border-input accent-[hsl(var(--primary))]"
                  />
                  Exclude excused from the total
                </label>
              </div>

              {edits[policy.id] && (
                <Button
                  loading={save.isPending}
                  onClick={() => save.mutate({ id: policy.id, payload: edits[policy.id] })}
                >
                  Save policy
                </Button>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function GradingTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['grade-scales'],
    queryFn: () => api.get<any[]>('/grade-scales'),
  });

  if (isLoading) return <LoadingState rows={3} />;
  const scales = toList(data);

  return (
    <div className="space-y-4">
      <Alert tone="default" title="Grade boundaries are configurable">
        Every result percentage is mapped through these bands. Editing a boundary changes future
        recalculations, not published records.
      </Alert>

      {scales.map((scale: any) => (
        <Card key={scale.id}>
          <CardHeader>
            <CardTitle>
              {scale.name}
              {scale.is_default && (
                <Badge tone="default" className="ml-2">
                  default
                </Badge>
              )}
            </CardTitle>
            <p className="text-sm text-muted-foreground">{scale.description}</p>
          </CardHeader>
          <CardContent>
            <Table>
              <THead>
                <TR>
                  <TH>Grade</TH>
                  <TH className="text-right">From (%)</TH>
                  <TH className="text-right">To (%)</TH>
                  <TH className="text-right">Grade point</TH>
                  <TH>Description</TH>
                  <TH>Pass</TH>
                </TR>
              </THead>
              <TBody>
                {scale.bands.map((band: any) => (
                  <TR key={band.id}>
                    <TD>
                      <Badge tone={band.is_pass ? 'success' : 'danger'}>{band.letter}</Badge>
                    </TD>
                    <TD className="text-right tabular-nums">{band.min_percentage}</TD>
                    <TD className="text-right tabular-nums">{band.max_percentage}</TD>
                    <TD className="text-right tabular-nums">{band.grade_point}</TD>
                    <TD className="text-muted-foreground">{band.description}</TD>
                    <TD>{band.is_pass ? 'Yes' : 'No'}</TD>
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

function RiskRulesTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['risk-rules'],
    queryFn: () => api.get<any[]>('/analytics/risk-rules'),
  });

  if (isLoading) return <LoadingState rows={3} />;
  const rules = toList(data);

  return (
    <div className="space-y-4">
      <Alert tone="warning" title="Academic Support Risk Indicator">
        These rules are the whole model. There is no hidden scoring — each triggered rule adds its
        weight, and every contributing factor is shown to the staff member reviewing the student.
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Active rules</CardTitle>
          <p className="text-sm text-muted-foreground">
            Total possible score: {rules.reduce((sum: number, rule: any) => sum + rule.weight, 0)}
          </p>
        </CardHeader>
        <CardContent>
          <Table>
            <THead>
              <TR>
                <TH>Rule</TH>
                <TH>Metric</TH>
                <TH>Condition</TH>
                <TH className="text-right">Threshold</TH>
                <TH className="text-right">Weight</TH>
                <TH>Scope</TH>
              </TR>
            </THead>
            <TBody>
              {rules.map((rule: any) => (
                <TR key={rule.id}>
                  <TD>
                    <p className="font-medium">{rule.label}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">{rule.code}</p>
                  </TD>
                  <TD className="text-muted-foreground">{rule.metric_display}</TD>
                  <TD className="text-muted-foreground">{rule.operator_display}</TD>
                  <TD className="text-right tabular-nums">{rule.threshold}</TD>
                  <TD className="text-right">
                    <Badge tone="muted">+{rule.weight}</Badge>
                  </TD>
                  <TD className="text-muted-foreground">
                    {rule.department ? 'Department' : 'Institution'}
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
