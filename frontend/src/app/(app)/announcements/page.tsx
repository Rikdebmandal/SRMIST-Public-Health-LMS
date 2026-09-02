'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pin, Plus } from 'lucide-react';
import { useState } from 'react';
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
import { formatDate, statusTone } from '@/lib/utils';
import type { Announcement } from '@/types';

export default function AnnouncementsPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [composing, setComposing] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['announcements'],
    queryFn: () => api.get<Paginated<Announcement>>('/announcements?page_size=50'),
  });

  const markRead = useMutation({
    mutationFn: (id: string) => api.post(`/announcements/${id}/mark-read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['announcements'] }),
  });

  const announcements = toList(data);

  return (
    <>
      <PageHeader
        title="Announcements"
        description="Notices targeted to you by the school, your department and your courses."
        actions={
          can('announcement.manage') && (
            <Button onClick={() => setComposing(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              New announcement
            </Button>
          )
        }
      />

      {isLoading && <LoadingState rows={3} />}
      {error && (
        <ErrorState message="Announcements could not be loaded." onRetry={() => refetch()} />
      )}
      {!isLoading && !error && announcements.length === 0 && (
        <EmptyState title="No announcements" description="You are all caught up." />
      )}

      <div className="space-y-3">
        {announcements.map((announcement) => (
          <Card key={announcement.id} className={announcement.is_read ? '' : 'border-primary/30'}>
            <CardContent className="pt-4 sm:pt-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  {announcement.is_pinned && (
                    <Pin className="h-3.5 w-3.5 text-primary" aria-label="Pinned" />
                  )}
                  <Badge tone={statusTone(announcement.priority)}>
                    {announcement.priority.toLowerCase()}
                  </Badge>
                  {announcement.category_name && (
                    <Badge tone="muted">{announcement.category_name}</Badge>
                  )}
                  {!announcement.is_read && <Badge tone="default">New</Badge>}
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatDate(announcement.publish_at)}
                </span>
              </div>

              <h2 className="mt-2 font-medium">{announcement.title}</h2>
              <p className="mt-1.5 whitespace-pre-line text-sm text-muted-foreground">
                {announcement.body}
              </p>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
                <span>
                  {announcement.author_name || 'Administration'}
                  {announcement.department_name ? ` · ${announcement.department_name}` : ''}
                </span>
                {!announcement.is_read && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => markRead.mutate(announcement.id)}
                  >
                    Mark as read
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {composing && <ComposeModal onClose={() => setComposing(false)} />}
    </>
  );
}

function ComposeModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [form, setForm] = useState({
    title: '',
    body: '',
    priority: 'NORMAL',
    audience: 'DEPARTMENT',
    is_pinned: false,
  });

  const publish = useMutation({
    mutationFn: async () => {
      const created = await api.post<Announcement>('/announcements', {
        ...form,
        department: form.audience === 'DEPARTMENT' ? user?.department : null,
        publish_at: new Date().toISOString(),
      });
      await api.post(`/announcements/${created.id}/publish`);
      return created;
    },
    onSuccess: () => {
      toast.success('Announcement published and recipients notified');
      queryClient.invalidateQueries({ queryKey: ['announcements'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The announcement could not be published.');
      }
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="New announcement"
      description="Publishing notifies everyone in the selected audience."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={publish.isPending}
            disabled={!form.title.trim() || !form.body.trim()}
            onClick={() => publish.mutate()}
          >
            Publish
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Title" required>
          {(props) => (
            <Input
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              {...props}
            />
          )}
        </Field>

        <Field label="Message" required>
          {(props) => (
            <Textarea
              value={form.body}
              onChange={(event) => setForm({ ...form, body: event.target.value })}
              rows={6}
              {...props}
            />
          )}
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Priority">
            {(props) => (
              <Select
                value={form.priority}
                onChange={(event) => setForm({ ...form, priority: event.target.value })}
                {...props}
              >
                <option value="NORMAL">Normal</option>
                <option value="IMPORTANT">Important</option>
                <option value="URGENT">Urgent</option>
              </Select>
            )}
          </Field>

          <Field label="Audience">
            {(props) => (
              <Select
                value={form.audience}
                onChange={(event) => setForm({ ...form, audience: event.target.value })}
                {...props}
              >
                <option value="DEPARTMENT">My department</option>
                <option value="SCHOOL">School-wide</option>
                <option value="INSTITUTION">Institution-wide</option>
              </Select>
            )}
          </Field>
        </div>
      </div>
    </Modal>
  );
}
