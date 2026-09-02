'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Briefcase, Building2, Calendar, ExternalLink, MapPin, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import {
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
  Textarea,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate, relativeTime } from '@/lib/utils';
import type { JobPosting } from '@/types';

export default function JobsPage() {
  const { can } = useAuth();
  const [type, setType] = useState('');
  const [posting, setPosting] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.get<Paginated<JobPosting>>('/jobs?page_size=50'),
  });

  const jobs = toList(data);
  const filtered = useMemo(
    () => jobs.filter((job) => !type || job.opportunity_type === type),
    [jobs, type],
  );

  return (
    <>
      <PageHeader
        title="Opportunities"
        description="Jobs, internships, research posts and fellowships shared with the school."
        actions={
          can('job.manage') && (
            <Button onClick={() => setPosting(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              Post an opportunity
            </Button>
          )
        }
      />

      <div className="mb-5 flex flex-wrap gap-1.5">
        {[
          ['', 'All'],
          ['JOB', 'Jobs'],
          ['INTERNSHIP', 'Internships'],
          ['RESEARCH', 'Research'],
          ['FELLOWSHIP', 'Fellowships'],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setType(value)}
            aria-pressed={type === value}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              type === value
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-muted'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Opportunities could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && filtered.length === 0 && (
        <EmptyState title="No open opportunities" description="Check back soon." />
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        {filtered.map((job) => (
          <Card key={job.id} className="flex flex-col">
            <CardContent className="flex flex-1 flex-col pt-4 sm:pt-5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="font-medium">{job.title}</h2>
                  <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Building2 className="h-3.5 w-3.5" aria-hidden />
                    {job.organization}
                  </p>
                </div>
                <Badge tone={job.is_open ? 'success' : 'muted'} className="shrink-0">
                  {job.type_display}
                </Badge>
              </div>

              <p className="mt-2 line-clamp-3 flex-1 text-sm text-muted-foreground">
                {job.description}
              </p>

              {job.skills_required?.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1">
                  {job.skills_required.slice(0, 5).map((skill) => (
                    <Badge key={skill} tone="muted">
                      {skill}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {job.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" aria-hidden />
                    {job.location}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Briefcase className="h-3 w-3" aria-hidden />
                  {job.mode_display}
                </span>
                {job.deadline && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" aria-hidden />
                    Closes {formatDate(job.deadline)} ({relativeTime(job.deadline)})
                  </span>
                )}
              </div>

              {job.eligibility && (
                <p className="mt-2 rounded-md bg-muted p-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Eligibility: </span>
                  {job.eligibility}
                </p>
              )}

              <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3">
                <span className="truncate text-xs text-muted-foreground">
                  Posted by {job.posted_by_detail?.full_name ?? 'Administration'}
                </span>
                {job.application_url ? (
                  <a
                    href={job.application_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    Apply
                    <ExternalLink className="h-3 w-3" aria-hidden />
                  </a>
                ) : (
                  job.contact_email && (
                    <a
                      href={`mailto:${job.contact_email}`}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      Contact
                    </a>
                  )
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {posting && <PostJobModal onClose={() => setPosting(false)} />}
    </>
  );
}

function PostJobModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title: '',
    organization: '',
    opportunity_type: 'JOB',
    work_mode: 'ONSITE',
    location: '',
    description: '',
    eligibility: '',
    application_url: '',
    contact_email: '',
    deadline: '',
  });

  const create = useMutation({
    mutationFn: () =>
      api.post('/jobs', {
        ...form,
        deadline: form.deadline || null,
        skills_required: [],
      }),
    onSuccess: () => {
      toast.success('Opportunity published');
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The opportunity could not be published.');
      }
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Post an opportunity"
      description="Visible to students, scholars and alumni across the school."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={create.isPending}
            disabled={!form.title.trim() || !form.organization.trim() || !form.description.trim()}
            onClick={() => create.mutate()}
          >
            Publish
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Role title" required>
          {(props) => (
            <Input
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <Field label="Organisation" required>
          {(props) => (
            <Input
              value={form.organization}
              onChange={(event) => setForm({ ...form, organization: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type">
            {(props) => (
              <Select
                value={form.opportunity_type}
                onChange={(event) => setForm({ ...form, opportunity_type: event.target.value })}
                {...props}
              >
                <option value="JOB">Job</option>
                <option value="INTERNSHIP">Internship</option>
                <option value="RESEARCH">Research opportunity</option>
                <option value="FELLOWSHIP">Fellowship</option>
              </Select>
            )}
          </Field>
          <Field label="Work mode">
            {(props) => (
              <Select
                value={form.work_mode}
                onChange={(event) => setForm({ ...form, work_mode: event.target.value })}
                {...props}
              >
                <option value="ONSITE">On-site</option>
                <option value="REMOTE">Remote</option>
                <option value="HYBRID">Hybrid</option>
              </Select>
            )}
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Location">
            {(props) => (
              <Input
                value={form.location}
                onChange={(event) => setForm({ ...form, location: event.target.value })}
                {...props}
              />
            )}
          </Field>
          <Field label="Application deadline">
            {(props) => (
              <Input
                type="date"
                value={form.deadline}
                onChange={(event) => setForm({ ...form, deadline: event.target.value })}
                {...props}
              />
            )}
          </Field>
        </div>
        <Field label="Description" required>
          {(props) => (
            <Textarea
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              rows={4}
              {...props}
            />
          )}
        </Field>
        <Field label="Eligibility">
          {(props) => (
            <Textarea
              value={form.eligibility}
              onChange={(event) => setForm({ ...form, eligibility: event.target.value })}
              rows={2}
              {...props}
            />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Application URL">
            {(props) => (
              <Input
                type="url"
                value={form.application_url}
                onChange={(event) => setForm({ ...form, application_url: event.target.value })}
                placeholder="https://…"
                {...props}
              />
            )}
          </Field>
          <Field label="Contact email">
            {(props) => (
              <Input
                type="email"
                value={form.contact_email}
                onChange={(event) => setForm({ ...form, contact_email: event.target.value })}
                {...props}
              />
            )}
          </Field>
        </div>
      </div>
    </Modal>
  );
}
