'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Briefcase, ExternalLink, MapPin, Search, UserCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
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
  Textarea,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { relativeTime } from '@/lib/utils';
import type { AlumniProfile, UserBrief } from '@/types';

interface AlumniRow extends AlumniProfile {
  user?: UserBrief;
  user_name?: string;
}

export default function AlumniPage() {
  const { can } = useAuth();
  const [term, setTerm] = useState('');
  const [mentorsOnly, setMentorsOnly] = useState(false);
  const [requestTarget, setRequestTarget] = useState<AlumniRow | null>(null);
  const canRequestMentorship = can('mentorship.participate');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['alumni-profiles'],
    queryFn: () => api.get<Paginated<AlumniRow>>('/alumni/profiles?page_size=100'),
  });

  const usersQuery = useQuery({
    queryKey: ['alumni-users'],
    queryFn: () => api.get<Paginated<any>>('/users?role=ALUMNI&page_size=100'),
    enabled: can('user.view'),
  });

  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    toList(usersQuery.data).forEach((user: any) => map.set(user.id, user.full_name));
    return map;
  }, [usersQuery.data]);

  const profiles = toList(data);

  const filtered = profiles.filter((profile) => {
    const name = profile.user_name ?? nameById.get(String((profile as any).user)) ?? '';
    const haystack = `${name} ${profile.current_organization} ${profile.job_title} ${profile.location}`.toLowerCase();
    const matchesTerm = !term || haystack.includes(term.toLowerCase());
    const matchesMentor = !mentorsOnly || profile.is_available_for_mentorship;
    return matchesTerm && matchesMentor;
  });

  return (
    <>
      <PageHeader
        title="Alumni directory"
        description="Graduates who have chosen to appear in the directory. Contact details stay private unless shared."
      />

      <Card className="mb-5">
        <CardContent className="flex flex-col gap-2 pt-4 sm:flex-row sm:items-center sm:pt-5">
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search by name, organisation or location"
              aria-label="Search alumni"
              className="pl-9"
            />
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={mentorsOnly}
              onChange={(event) => setMentorsOnly(event.target.checked)}
              className="h-4 w-4 rounded border-input accent-[hsl(var(--primary))]"
            />
            Available for mentorship
          </label>
        </CardContent>
      </Card>

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="The directory could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && filtered.length === 0 && (
        <EmptyState
          title="No alumni found"
          description="Try a different search, or clear the mentorship filter."
        />
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((profile) => {
          const name =
            profile.user_name ?? nameById.get(String((profile as any).user)) ?? 'Alumnus';
          return (
            <Card key={profile.id} className="flex flex-col p-4">
              <div className="flex items-start gap-3">
                <Avatar name={name} size="lg" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{name}</p>
                  <p className="text-xs text-muted-foreground">
                    Class of {profile.graduation_year}
                    {profile.program_name ? ` · ${profile.program_name}` : ''}
                  </p>
                </div>
              </div>

              <div className="mt-3 space-y-1 text-sm">
                {profile.job_title && (
                  <p className="flex items-center gap-1.5">
                    <Briefcase className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="truncate">
                      {profile.job_title}
                      {profile.current_organization ? ` at ${profile.current_organization}` : ''}
                    </span>
                  </p>
                )}
                {profile.location && (
                  <p className="flex items-center gap-1.5 text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    <span className="truncate">{profile.location}</span>
                  </p>
                )}
              </div>

              {profile.skills?.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1">
                  {profile.skills.slice(0, 4).map((skill) => (
                    <Badge key={skill} tone="muted">
                      {skill}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="mt-auto flex items-center justify-between gap-2 border-t border-border pt-3">
                {profile.is_available_for_mentorship ? (
                  <Badge tone="success">
                    <UserCheck className="h-3 w-3" aria-hidden />
                    Mentoring
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">Not mentoring</span>
                )}
                <div className="flex items-center gap-2">
                  {profile.linkedin_url && (
                    <a
                      href={profile.linkedin_url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`${name} on LinkedIn`}
                      className="text-muted-foreground hover:text-primary"
                    >
                      <ExternalLink className="h-4 w-4" aria-hidden />
                    </a>
                  )}
                  {profile.is_available_for_mentorship && canRequestMentorship && (
                    <Button size="sm" variant="outline" onClick={() => setRequestTarget(profile)}>
                      Request mentorship
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {requestTarget && (
        <MentorshipModal
          mentorId={String((requestTarget as any).user)}
          mentorName={
            requestTarget.user_name ??
            nameById.get(String((requestTarget as any).user)) ??
            'this alumnus'
          }
          onClose={() => setRequestTarget(null)}
        />
      )}

      <MyRequests />
    </>
  );
}

function MentorshipModal({
  mentorId,
  mentorName,
  onClose,
}: {
  mentorId: string;
  mentorName: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState('');
  const [message, setMessage] = useState('');

  const create = useMutation({
    mutationFn: () => api.post('/mentorship', { mentor: mentorId, topic, message }),
    onSuccess: () => {
      toast.success('Mentorship request sent');
      queryClient.invalidateQueries({ queryKey: ['mentorship'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The request could not be sent.');
      }
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={`Request mentorship from ${mentorName}`}
      description="They will see your name and message, and can accept or decline."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={create.isPending}
            disabled={!topic.trim()}
            onClick={() => create.mutate()}
          >
            Send request
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Topic" required>
          {(props) => (
            <Input
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="e.g. Careers in health data analytics"
              {...props}
            />
          )}
        </Field>
        <Field label="Message">
          {(props) => (
            <Textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={5}
              placeholder="Introduce yourself and say what you would like to discuss."
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}

function MyRequests() {
  const queryClient = useQueryClient();
  const { can } = useAuth();
  // The Dean and HOD can browse the directory but hold no mentorship
  // permission, so skip the request entirely rather than provoking a 403.
  const canParticipate = can('mentorship.participate');

  const { data } = useQuery({
    queryKey: ['mentorship'],
    queryFn: () => api.get<Paginated<any>>('/mentorship'),
    enabled: canParticipate,
  });

  const respond = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.post(`/mentorship/${id}/respond`, { status }),
    onSuccess: () => {
      toast.success('Response recorded');
      queryClient.invalidateQueries({ queryKey: ['mentorship'] });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Could not record the response.'),
  });

  const requests = toList(data);
  if (requests.length === 0) return null;

  return (
    <section className="mt-8">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Mentorship requests
      </h2>
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <ul className="divide-y divide-border">
            {requests.map((request: any) => (
              <li
                key={request.id}
                className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{request.topic}</p>
                  <p className="text-xs text-muted-foreground">
                    {request.requester_detail?.full_name} → {request.mentor_detail?.full_name} ·{' '}
                    {relativeTime(request.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    tone={
                      request.status === 'ACCEPTED'
                        ? 'success'
                        : request.status === 'DECLINED'
                          ? 'danger'
                          : 'warning'
                    }
                  >
                    {request.status.toLowerCase()}
                  </Badge>
                  {request.status === 'PENDING' && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => respond.mutate({ id: request.id, status: 'ACCEPTED' })}
                      >
                        Accept
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => respond.mutate({ id: request.id, status: 'DECLINED' })}
                      >
                        Decline
                      </Button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}
