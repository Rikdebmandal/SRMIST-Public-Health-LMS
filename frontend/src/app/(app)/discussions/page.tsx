'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, MessageSquare, Pin, Plus, ThumbsUp } from 'lucide-react';
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
  Textarea,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { relativeTime } from '@/lib/utils';
import type { CourseSection, DiscussionThread } from '@/types';

export default function DiscussionsPage() {
  const [asking, setAsking] = useState(false);
  const [openThread, setOpenThread] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['threads'],
    queryFn: () => api.get<Paginated<DiscussionThread>>('/threads?page_size=50'),
  });

  const threads = toList(data);

  return (
    <>
      <PageHeader
        title="Discussions"
        description="Course question-and-answer threads, moderated by your faculty."
        actions={
          <Button onClick={() => setAsking(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Ask a question
          </Button>
        }
      />

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Discussions could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && threads.length === 0 && (
        <EmptyState
          title="No discussions yet"
          description="Be the first to ask a question in one of your courses."
        />
      )}

      <div className="space-y-3">
        {threads.map((thread) => (
          <Card
            key={thread.id}
            className="cursor-pointer transition-colors hover:border-primary/40"
            onClick={() => setOpenThread(thread.id)}
          >
            <CardContent className="pt-4 sm:pt-5">
              <div className="flex items-start gap-3">
                <Avatar name={thread.author_detail.full_name} size="md" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {thread.is_pinned && (
                      <Pin className="h-3.5 w-3.5 text-primary" aria-label="Pinned" />
                    )}
                    <Badge tone="muted">{thread.course_code}</Badge>
                    <Badge
                      tone={
                        thread.status === 'ANSWERED'
                          ? 'success'
                          : thread.status === 'CLOSED'
                            ? 'muted'
                            : 'default'
                      }
                    >
                      {thread.status.toLowerCase()}
                    </Badge>
                  </div>
                  <h2 className="mt-1.5 font-medium">{thread.title}</h2>
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{thread.body}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>{thread.author_detail.full_name}</span>
                    <span>{relativeTime(thread.created_at)}</span>
                    <span className="flex items-center gap-1">
                      <MessageSquare className="h-3 w-3" aria-hidden />
                      {thread.reply_count}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {asking && <AskModal onClose={() => setAsking(false)} />}
      {openThread && <ThreadModal threadId={openThread} onClose={() => setOpenThread(null)} />}
    </>
  );
}

function AskModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ section: '', title: '', body: '' });

  const sectionsQuery = useQuery({
    queryKey: ['my-courses'],
    queryFn: () => api.get<CourseSection[]>('/courses/my-courses'),
  });

  const create = useMutation({
    mutationFn: () => api.post('/threads', form),
    onSuccess: () => {
      toast.success('Question posted');
      queryClient.invalidateQueries({ queryKey: ['threads'] });
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The question could not be posted.'),
  });

  const sections = sectionsQuery.data ?? [];

  return (
    <Modal
      open
      onClose={onClose}
      title="Ask a question"
      description="Your question is visible to everyone in the selected course section."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={create.isPending}
            disabled={!form.section || form.title.trim().length < 5 || !form.body.trim()}
            onClick={() => create.mutate()}
          >
            Post question
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Course section" required>
          {(props) => (
            <Select
              value={form.section}
              onChange={(event) => setForm({ ...form, section: event.target.value })}
              {...props}
            >
              <option value="">Choose a section…</option>
              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.course_code} — {section.course_name}
                </option>
              ))}
            </Select>
          )}
        </Field>

        <Field label="Title" required hint="At least five characters.">
          {(props) => (
            <Input
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder="Summarise your question"
              {...props}
            />
          )}
        </Field>

        <Field label="Details" required>
          {(props) => (
            <Textarea
              value={form.body}
              onChange={(event) => setForm({ ...form, body: event.target.value })}
              rows={6}
              placeholder="Explain what you have tried and where you are stuck."
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}

function ThreadModal({ threadId, onClose }: { threadId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { user, can } = useAuth();
  const [reply, setReply] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['thread', threadId],
    queryFn: () => api.get<DiscussionThread>(`/threads/${threadId}`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['thread', threadId] });
    queryClient.invalidateQueries({ queryKey: ['threads'] });
  };

  const postReply = useMutation({
    mutationFn: () => api.post('/replies', { thread: threadId, body: reply }),
    onSuccess: () => {
      setReply('');
      invalidate();
      toast.success('Reply posted');
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'The reply could not be posted.'),
  });

  const vote = useMutation({
    mutationFn: (replyId: string) => api.post(`/replies/${replyId}/helpful`),
    onSuccess: invalidate,
  });

  const accept = useMutation({
    mutationFn: (replyId: string) => api.post(`/replies/${replyId}/accept`),
    onSuccess: () => {
      invalidate();
      toast.success('Answer accepted');
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : 'Could not accept this answer.'),
  });

  const canAccept = data && (data.author === user?.id || can('forum.moderate'));

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={data?.title ?? 'Discussion'}
      description={data ? `${data.course_code} · ${relativeTime(data.created_at)}` : undefined}
      footer={
        <div className="flex w-full flex-col gap-2 sm:flex-row">
          <Textarea
            value={reply}
            onChange={(event) => setReply(event.target.value)}
            rows={2}
            placeholder="Write a reply…"
            aria-label="Write a reply"
            className="flex-1"
          />
          <Button
            loading={postReply.isPending}
            disabled={reply.trim().length < 2}
            onClick={() => postReply.mutate()}
          >
            Reply
          </Button>
        </div>
      }
    >
      {isLoading || !data ? (
        <LoadingState rows={4} />
      ) : (
        <div className="space-y-4">
          <div className="flex gap-3">
            <Avatar name={data.author_detail.full_name} size="md" />
            <div className="min-w-0">
              <p className="text-sm font-medium">{data.author_detail.full_name}</p>
              <p className="text-xs text-muted-foreground">
                {data.author_detail.role_display} · {relativeTime(data.created_at)}
              </p>
              <p className="mt-2 whitespace-pre-line text-sm">{data.body}</p>
            </div>
          </div>

          <div className="border-t border-border pt-4">
            <h3 className="mb-3 text-sm font-semibold">
              {data.replies?.length ?? 0} {data.replies?.length === 1 ? 'reply' : 'replies'}
            </h3>
            {data.replies?.length === 0 && (
              <EmptyState title="No replies yet" description="Be the first to help." />
            )}
            <ul className="space-y-4">
              {data.replies?.map((item) => (
                <li
                  key={item.id}
                  className={
                    item.is_accepted_answer
                      ? 'rounded-lg border border-success/40 bg-success/5 p-3'
                      : ''
                  }
                >
                  <div className="flex gap-3">
                    <Avatar name={item.author_detail.full_name} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium">{item.author_detail.full_name}</p>
                        <Badge tone="muted">{item.author_detail.role_display}</Badge>
                        {item.is_accepted_answer && (
                          <Badge tone="success">Accepted answer</Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {relativeTime(item.created_at)}
                        </span>
                      </div>
                      <p className="mt-1.5 whitespace-pre-line text-sm">{item.body}</p>
                      <div className="mt-2 flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => vote.mutate(item.id)}
                          aria-pressed={item.has_voted}
                        >
                          <ThumbsUp
                            className={`h-3.5 w-3.5 ${item.has_voted ? 'text-primary' : ''}`}
                            aria-hidden
                          />
                          {item.helpful_count}
                        </Button>
                        {canAccept && !item.is_accepted_answer && (
                          <Button size="sm" variant="ghost" onClick={() => accept.mutate(item.id)}>
                            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                            Accept
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Modal>
  );
}
