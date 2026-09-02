'use client';

import { useQuery } from '@tanstack/react-query';
import { Download, Info } from 'lucide-react';
import { toast } from 'sonner';

import {
  CategoryBarChart,
  CorrelationScatter,
  DonutChart,
  useToneColors,
} from '@/components/charts';
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
  LoadingState,
  PageHeader,
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
import { ApiError, api, downloadFile } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { percent } from '@/lib/utils';
import type { RiskOutcome } from '@/types';

export default function AnalyticsPage() {
  const { can } = useAuth();

  return (
    <>
      <PageHeader
        title="Analytics workspace"
        description="Descriptive analytics across attendance, assessment and engagement."
        actions={
          can('report.export') && (
            <Button
              variant="outline"
              onClick={() =>
                downloadFile('/exports/at-risk', 'academic-support-indicators.csv').catch((error) =>
                  toast.error(error instanceof ApiError ? error.message : 'Export failed.'),
                )
              }
            >
              <Download className="h-4 w-4" aria-hidden />
              Export indicators
            </Button>
          )
        }
      />

      <Tabs defaultValue="correlation">
        <TabsList>
          <TabsTrigger value="correlation">Attendance vs performance</TabsTrigger>
          <TabsTrigger value="grades">Grade distribution</TabsTrigger>
          <TabsTrigger value="submissions">Submission rates</TabsTrigger>
          {can('risk.view') && <TabsTrigger value="risk">Academic support</TabsTrigger>}
        </TabsList>

        <TabsContent value="correlation">
          <CorrelationTab />
        </TabsContent>
        <TabsContent value="grades">
          <GradesTab />
        </TabsContent>
        <TabsContent value="submissions">
          <SubmissionsTab />
        </TabsContent>
        {can('risk.view') && (
          <TabsContent value="risk">
            <RiskTab />
          </TabsContent>
        )}
      </Tabs>
    </>
  );
}

function CorrelationTab() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['analytics', 'correlation'],
    queryFn: () =>
      api.get<{ points: any[]; sample_size: number; pearson_r: number | null; note: string }>(
        '/analytics/workspace/attendance-vs-performance',
      ),
  });

  if (isLoading) return <LoadingState rows={3} />;
  if (error || !data) {
    return <ErrorState message="This view could not be loaded." onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Students in sample" value={data.sample_size} />
        <StatCard
          label="Pearson r"
          value={data.pearson_r === null ? '—' : data.pearson_r.toFixed(3)}
          hint="Attendance vs mean result"
        />
        <StatCard
          label="Relationship"
          value={
            data.pearson_r === null
              ? '—'
              : Math.abs(data.pearson_r) > 0.5
                ? 'Moderate+'
                : Math.abs(data.pearson_r) > 0.3
                  ? 'Weak'
                  : 'Negligible'
          }
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Attendance against mean result</CardTitle>
          <p className="text-sm text-muted-foreground">
            Each point is one student. Labels are enrolment numbers, not names.
          </p>
        </CardHeader>
        <CardContent>
          {data.points.length > 0 ? (
            <CorrelationScatter points={data.points} />
          ) : (
            <EmptyState title="Not enough data" description="Results and attendance are needed." />
          )}
          <Alert tone="default" className="mt-4">
            <span className="flex items-start gap-1.5">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {data.note}
            </span>
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}

function GradesTab() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['analytics', 'grades'],
    queryFn: () => api.get<{ grade_letter: string; count: number }[]>(
      '/analytics/workspace/grade-distribution',
    ),
  });

  if (isLoading) return <LoadingState rows={3} />;
  if (error || !data) {
    return <ErrorState message="This view could not be loaded." onRetry={() => refetch()} />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Grade distribution</CardTitle>
        <p className="text-sm text-muted-foreground">Published course results by letter grade.</p>
      </CardHeader>
      <CardContent>
        {data.length > 0 ? (
          <div className="grid gap-5 lg:grid-cols-2">
            <CategoryBarChart
              data={data}
              xKey="grade_letter"
              yKey="count"
              label="Students"
              unit=""
              domain={[0, Math.max(...data.map((row) => row.count)) + 2]}
            />
            <DonutChart
              data={data.map((row) => ({ name: row.grade_letter, count: row.count }))}
              nameKey="name"
              valueKey="count"
            />
          </div>
        ) : (
          <EmptyState title="No results published yet" />
        )}
      </CardContent>
    </Card>
  );
}

function SubmissionsTab() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['analytics', 'submissions'],
    queryFn: () => api.get<any[]>('/analytics/workspace/submission-rates'),
  });

  if (isLoading) return <LoadingState rows={3} />;
  if (error || !data) {
    return <ErrorState message="This view could not be loaded." onRetry={() => refetch()} />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Assignment submission rates</CardTitle>
        <p className="text-sm text-muted-foreground">
          Share of enrolled students who submitted each published assignment.
        </p>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <EmptyState title="No published assignments yet" />
        ) : (
          <>
            <div className="mb-5">
              <CategoryBarChart
                data={data.slice(0, 12).map((row) => ({
                  ...row,
                  label: row.course,
                  status: row.rate < 60 ? 'critical' : row.rate < 80 ? 'warning' : 'ok',
                }))}
                xKey="label"
                yKey="rate"
                label="Submission rate"
                colorByStatus
                referenceValue={80}
              />
            </div>
            <Table>
              <THead>
                <TR>
                  <TH>Assignment</TH>
                  <TH>Course</TH>
                  <TH className="text-right">Enrolled</TH>
                  <TH className="text-right">Submitted</TH>
                  <TH className="text-right">Rate</TH>
                </TR>
              </THead>
              <TBody>
                {data.map((row, index) => (
                  <TR key={index}>
                    <TD className="max-w-[280px] truncate">{row.assignment}</TD>
                    <TD className="font-mono text-xs">{row.course}</TD>
                    <TD className="text-right tabular-nums">{row.enrolled}</TD>
                    <TD className="text-right tabular-nums">{row.submitted}</TD>
                    <TD className="text-right">
                      <Badge
                        tone={row.rate < 60 ? 'danger' : row.rate < 80 ? 'warning' : 'success'}
                      >
                        {percent(row.rate, 0)}
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
  );
}

function RiskTab() {
  const tones = useToneColors();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['analytics', 'risk-students'],
    queryFn: () =>
      api.get<{
        indicator_name: string;
        disclaimer: string;
        count: number;
        students: RiskOutcome[];
      }>('/analytics/risk/students?level=low'),
  });

  if (isLoading) return <LoadingState rows={4} />;
  if (error || !data) {
    return <ErrorState message="This view could not be loaded." onRetry={() => refetch()} />;
  }

  const distribution = ['low', 'moderate', 'high', 'critical'].map((level) => ({
    name: level.charAt(0).toUpperCase() + level.slice(1),
    count: data.students.filter((student) => student.level === level).length,
  }));

  return (
    <div className="space-y-5">
      <Alert tone="warning" title={data.indicator_name}>
        {data.disclaimer}
      </Alert>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <DonutChart
              data={distribution}
              nameKey="name"
              valueKey="count"
              colors={[tones.ok, tones.warning, tones.high, tones.critical]}
            />
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Students by indicator score</CardTitle>
            <p className="text-sm text-muted-foreground">
              Every contributing factor is listed so you can verify the reasoning.
            </p>
          </CardHeader>
          <CardContent>
            {data.students.length === 0 ? (
              <EmptyState title="No indicators raised" />
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Student</TH>
                    <TH className="text-right">Score</TH>
                    <TH>Level</TH>
                    <TH>Contributing factors</TH>
                  </TR>
                </THead>
                <TBody>
                  {data.students
                    .filter((student) => student.level !== 'low')
                    .map((student) => (
                      <TR key={student.student?.id}>
                        <TD>
                          <p className="max-w-[160px] truncate font-medium">
                            {student.student?.full_name}
                          </p>
                          <p className="font-mono text-xs text-muted-foreground">
                            {student.student?.enrollment_number}
                          </p>
                        </TD>
                        <TD className="text-right font-semibold tabular-nums">{student.score}</TD>
                        <TD>
                          <Badge
                            tone={
                              student.level === 'critical' || student.level === 'high'
                                ? 'danger'
                                : student.level === 'moderate'
                                  ? 'warning'
                                  : 'success'
                            }
                          >
                            {student.level_label}
                          </Badge>
                        </TD>
                        <TD>
                          <ul className="space-y-0.5">
                            {student.factors.map((factor) => (
                              <li key={factor.code} className="text-xs text-muted-foreground">
                                {factor.label} ({factor.observed} vs {factor.threshold})
                              </li>
                            ))}
                          </ul>
                        </TD>
                      </TR>
                    ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
