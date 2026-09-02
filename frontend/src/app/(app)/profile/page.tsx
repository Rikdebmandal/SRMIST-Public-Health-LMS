'use client';

import { useQuery } from '@tanstack/react-query';

import { RiskPanel } from '@/components/risk-panel';
import {
  Avatar,
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  LoadingState,
  PageHeader,
} from '@/components/ui';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/utils';
import type { RiskOutcome } from '@/types';

export default function ProfilePage() {
  const { user, loading, hasRole } = useAuth();

  const riskQuery = useQuery({
    queryKey: ['risk', 'me'],
    queryFn: () => api.get<RiskOutcome>('/analytics/risk/me'),
    enabled: hasRole('STUDENT'),
  });

  if (loading || !user) return <LoadingState rows={4} />;

  const profile = user.profile as any;

  const roleFields: [string, string | number | undefined][] = (() => {
    switch (user.role) {
      case 'STUDENT':
        return [
          ['Enrolment number', profile?.enrollment_number],
          ['Program', profile?.program_name],
          ['Batch', profile?.batch_name],
          ['Current semester', profile?.current_semester],
          ['Admission date', profile?.admission_date ? formatDate(profile.admission_date) : '—'],
        ];
      case 'FACULTY':
      case 'ADMIN':
      case 'DEAN':
        return [
          ['Employee id', profile?.employee_id],
          ['Designation', profile?.designation_display],
          ['Specialisation', profile?.specialization],
          ['Qualification', profile?.qualification],
          ['Office', profile?.office_location],
        ];
      case 'SCHOLAR':
        return [
          ['Registration number', profile?.registration_number],
          ['Research area', profile?.research_area],
          ['Supervisor', profile?.supervisor_name],
          ['Scholar type', profile?.scholar_type],
          ['Thesis title', profile?.thesis_title],
        ];
      case 'ALUMNI':
        return [
          ['Graduation year', profile?.graduation_year],
          ['Program', profile?.program_name],
          ['Organisation', profile?.current_organization],
          ['Role', profile?.job_title],
          ['Location', profile?.location],
        ];
      default:
        return [];
    }
  })();

  return (
    <>
      <PageHeader title="My profile" description="Your account and academic record." />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="pt-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <Avatar name={user.full_name} src={user.avatar} size="lg" className="h-16 w-16 text-lg" />
              <div className="min-w-0">
                <h2 className="text-lg font-semibold">{user.full_name}</h2>
                <p className="text-sm text-muted-foreground">{user.email}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="default">{user.role_display}</Badge>
                  {user.department_name && <Badge tone="muted">{user.department_name}</Badge>}
                  <Badge tone={user.is_active ? 'success' : 'danger'}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>
            </div>

            {user.bio && <p className="mt-4 text-sm text-muted-foreground">{user.bio}</p>}

            <dl className="mt-5 grid gap-x-6 gap-y-3 border-t border-border pt-5 sm:grid-cols-2">
              {[
                ['Phone', user.phone || '—'],
                ['Timezone', user.timezone_name],
                ['Joined', formatDate(user.date_joined)],
                ['Last active', user.last_active_at ? formatDate(user.last_active_at, true) : '—'],
                ...roleFields,
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
                  <dd className="mt-0.5 text-sm font-medium">{value || '—'}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <div className="space-y-5">
          {hasRole('STUDENT') && riskQuery.data && <RiskPanel risk={riskQuery.data} compact />}

          <Card>
            <CardHeader>
              <CardTitle>Your permissions</CardTitle>
              <p className="text-sm text-muted-foreground">
                What your role allows. The server enforces these on every request.
              </p>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {user.permissions.map((permission) => (
                  <Badge key={permission} tone="muted" className="font-mono text-[10px]">
                    {permission}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
