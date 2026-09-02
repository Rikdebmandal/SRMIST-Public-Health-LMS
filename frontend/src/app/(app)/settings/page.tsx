'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTheme } from 'next-themes';
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
  Field,
  Input,
  LoadingState,
  PageHeader,
  Select,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Preferences" description="Your profile, appearance and alerts." />

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>
        <TabsContent value="appearance">
          <AppearanceTab />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationsTab />
        </TabsContent>
        <TabsContent value="security">
          <SecurityTab />
        </TabsContent>
      </Tabs>
    </>
  );
}

function ProfileTab() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState({ phone: '', bio: '', timezone_name: 'Asia/Kolkata' });

  useEffect(() => {
    if (user) {
      setForm({
        phone: user.phone ?? '',
        bio: user.bio ?? '',
        timezone_name: user.timezone_name ?? 'Asia/Kolkata',
      });
    }
  }, [user]);

  const save = useMutation({
    mutationFn: () => api.patch('/auth/me', form),
    onSuccess: async () => {
      await refreshUser();
      toast.success('Profile updated');
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The profile could not be saved.'),
  });

  if (!user) return <LoadingState rows={3} />;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Contact details</CardTitle>
        <p className="text-sm text-muted-foreground">
          Your name, email and role are managed by your department administrator.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name" hint="Contact your administrator to change this.">
            {(props) => <Input value={user.full_name} disabled {...props} />}
          </Field>
          <Field label="Email" hint="Used for sign-in and notifications.">
            {(props) => <Input value={user.email} disabled {...props} />}
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Phone">
            {(props) => (
              <Input
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
                placeholder="+91 …"
                {...props}
              />
            )}
          </Field>
          <Field label="Timezone">
            {(props) => (
              <Select
                value={form.timezone_name}
                onChange={(event) => setForm({ ...form, timezone_name: event.target.value })}
                {...props}
              >
                <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                <option value="UTC">UTC</option>
                <option value="Asia/Dubai">Asia/Dubai</option>
                <option value="Europe/London">Europe/London</option>
                <option value="America/New_York">America/New_York</option>
              </Select>
            )}
          </Field>
        </div>

        <Field label="About you">
          {(props) => (
            <Textarea
              value={form.bio}
              onChange={(event) => setForm({ ...form, bio: event.target.value })}
              rows={4}
              {...props}
            />
          )}
        </Field>

        <Button loading={save.isPending} onClick={() => save.mutate()}>
          Save changes
        </Button>
      </CardContent>
    </Card>
  );
}

function AppearanceTab() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Theme</CardTitle>
        <p className="text-sm text-muted-foreground">
          Light, dark, or follow your device setting.
        </p>
      </CardHeader>
      <CardContent>
        {mounted && (
          <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
            {[
              { value: 'light', label: 'Light', preview: 'bg-white border-slate-200' },
              { value: 'dark', label: 'Dark', preview: 'bg-slate-900 border-slate-700' },
              {
                value: 'system',
                label: 'System',
                preview: 'bg-gradient-to-br from-white to-slate-900 border-slate-400',
              },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={theme === option.value}
                onClick={() => setTheme(option.value)}
                className={cn(
                  'rounded-lg border p-3 text-left transition-colors',
                  theme === option.value
                    ? 'border-primary ring-2 ring-primary/20'
                    : 'border-border hover:bg-muted',
                )}
              >
                <div className={cn('mb-2 h-14 w-full rounded-md border', option.preview)} />
                <span className="text-sm font-medium">{option.label}</span>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NotificationsTab() {
  const queryClient = useQueryClient();
  const [prefs, setPrefs] = useState<Record<string, { in_app: boolean; email: boolean }>>({});

  const catalogueQuery = useQuery({
    queryKey: ['notification-catalogue'],
    queryFn: () => api.get<{ code: string; label: string }[]>(
      '/notification-preferences/catalogue',
    ),
  });

  const currentQuery = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: () => api.get<any[]>('/notification-preferences'),
  });

  const digestQuery = useQuery({
    queryKey: ['digest-subscription'],
    queryFn: () => api.get<any>('/digest/subscription'),
  });

  useEffect(() => {
    if (currentQuery.data) {
      const map: Record<string, { in_app: boolean; email: boolean }> = {};
      currentQuery.data.forEach((row: any) => {
        map[row.event] = { in_app: row.in_app, email: row.email };
      });
      setPrefs(map);
    }
  }, [currentQuery.data]);

  const save = useMutation({
    mutationFn: () =>
      api.put('/notification-preferences/bulk', {
        preferences: Object.entries(prefs).map(([event, value]) => ({ event, ...value })),
      }),
    onSuccess: () => {
      toast.success('Notification preferences saved');
      queryClient.invalidateQueries({ queryKey: ['notification-preferences'] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Preferences could not be saved.'),
  });

  const saveDigest = useMutation({
    mutationFn: (frequency: string) => api.put('/digest/subscription', { frequency }),
    onSuccess: () => {
      toast.success('Digest preference saved');
      queryClient.invalidateQueries({ queryKey: ['digest-subscription'] });
    },
  });

  if (catalogueQuery.isLoading) return <LoadingState rows={4} />;

  const catalogue = catalogueQuery.data ?? [];

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Weekly academic digest</CardTitle>
          <p className="text-sm text-muted-foreground">
            A summary of new notes, deadlines, marks and attendance.
          </p>
        </CardHeader>
        <CardContent>
          <Field label="Delivery frequency">
            {(props) => (
              <Select
                value={digestQuery.data?.frequency ?? 'WEEKLY'}
                onChange={(event) => saveDigest.mutate(event.target.value)}
                className="sm:max-w-xs"
                {...props}
              >
                <option value="WEEKLY">Weekly</option>
                <option value="FORTNIGHTLY">Fortnightly</option>
                <option value="OFF">Off</option>
              </Select>
            )}
          </Field>
          {digestQuery.data?.last_sent_at && (
            <p className="mt-2 text-xs text-muted-foreground">
              Last sent {new Date(digestQuery.data.last_sent_at).toLocaleString()}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Event preferences</CardTitle>
          <p className="text-sm text-muted-foreground">
            Choose how each kind of alert reaches you.
          </p>
        </CardHeader>
        <CardContent>
          <div className="table-scroll scrollbar-thin">
            <table className="w-full text-sm">
              <thead className="border-b border-border">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 pr-3 font-semibold">Event</th>
                  <th className="pb-2 px-3 text-center font-semibold">In-app</th>
                  <th className="pb-2 pl-3 text-center font-semibold">Email</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {catalogue.map((event) => {
                  const current = prefs[event.code] ?? { in_app: true, email: false };
                  return (
                    <tr key={event.code}>
                      <td className="py-2.5 pr-3">{event.label}</td>
                      <td className="px-3 text-center">
                        <input
                          type="checkbox"
                          checked={current.in_app}
                          onChange={(e) =>
                            setPrefs({
                              ...prefs,
                              [event.code]: { ...current, in_app: e.target.checked },
                            })
                          }
                          aria-label={`In-app notifications for ${event.label}`}
                          className="h-4 w-4 rounded border-input accent-[hsl(var(--primary))]"
                        />
                      </td>
                      <td className="pl-3 text-center">
                        <input
                          type="checkbox"
                          checked={current.email}
                          onChange={(e) =>
                            setPrefs({
                              ...prefs,
                              [event.code]: { ...current, email: e.target.checked },
                            })
                          }
                          aria-label={`Email notifications for ${event.label}`}
                          className="h-4 w-4 rounded border-input accent-[hsl(var(--primary))]"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Button className="mt-4" loading={save.isPending} onClick={() => save.mutate()}>
            Save preferences
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function SecurityTab() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' });

  const change = useMutation({
    mutationFn: () =>
      api.post('/auth/password/change', {
        current_password: form.current_password,
        new_password: form.new_password,
      }),
    onSuccess: () => {
      toast.success('Password updated');
      setForm({ current_password: '', new_password: '', confirm: '' });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The password could not be changed.');
      }
    },
  });

  const mismatch = form.confirm.length > 0 && form.new_password !== form.confirm;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <p className="text-sm text-muted-foreground">
          Every password change is recorded in the audit log.
        </p>
      </CardHeader>
      <CardContent className="max-w-md space-y-4">
        <Field label="Current password" required>
          {(props) => (
            <Input
              type="password"
              autoComplete="current-password"
              value={form.current_password}
              onChange={(event) => setForm({ ...form, current_password: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <Field label="New password" required hint="At least 8 characters, not entirely numeric.">
          {(props) => (
            <Input
              type="password"
              autoComplete="new-password"
              value={form.new_password}
              onChange={(event) => setForm({ ...form, new_password: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <Field
          label="Confirm new password"
          required
          error={mismatch ? 'The passwords do not match.' : undefined}
        >
          {(props) => (
            <Input
              type="password"
              autoComplete="new-password"
              value={form.confirm}
              onChange={(event) => setForm({ ...form, confirm: event.target.value })}
              {...props}
            />
          )}
        </Field>

        <Button
          loading={change.isPending}
          disabled={
            !form.current_password || !form.new_password || mismatch || form.confirm.length === 0
          }
          onClick={() => change.mutate()}
        >
          Update password
        </Button>
      </CardContent>
    </Card>
  );
}
