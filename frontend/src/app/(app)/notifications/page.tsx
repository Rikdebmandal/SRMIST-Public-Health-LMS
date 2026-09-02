'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck } from 'lucide-react';
import Link from 'next/link';

import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from '@/components/ui';
import { api, toList, type Paginated } from '@/lib/api';
import { cn, relativeTime } from '@/lib/utils';
import type { NotificationItem } from '@/types';

const LEVEL_TONE = {
  INFO: 'default',
  SUCCESS: 'success',
  WARNING: 'warning',
  CRITICAL: 'danger',
} as const;

export default function NotificationsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<Paginated<NotificationItem>>('/notifications?page_size=50'),
  });

  const markRead = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => api.post('/notifications/read-all'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] });
    },
  });

  const notifications = toList(data);
  const unread = notifications.filter((item) => !item.is_read);

  return (
    <>
      <PageHeader
        title="Notifications"
        description={
          unread.length > 0 ? `${unread.length} unread` : 'You are up to date.'
        }
        actions={
          unread.length > 0 && (
            <Button variant="outline" loading={markAllRead.isPending} onClick={() => markAllRead.mutate()}>
              <CheckCheck className="h-4 w-4" aria-hidden />
              Mark all as read
            </Button>
          )
        }
      />

      {isLoading && <LoadingState rows={4} />}
      {error && <ErrorState message="Notifications could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && notifications.length === 0 && (
        <EmptyState
          icon={Bell}
          title="No notifications"
          description="Assignment, attendance and announcement alerts will appear here."
        />
      )}

      <div className="space-y-2">
        {notifications.map((notification) => (
          <Card
            key={notification.id}
            className={cn(!notification.is_read && 'border-primary/30 bg-primary/[0.03]')}
          >
            <CardContent className="pt-4 sm:pt-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={LEVEL_TONE[notification.level] ?? 'default'}>
                      {notification.event_display}
                    </Badge>
                    {!notification.is_read && <Badge tone="default">New</Badge>}
                  </div>
                  <p className="mt-1.5 font-medium">{notification.title}</p>
                  {notification.body && (
                    <p className="mt-1 whitespace-pre-line text-sm text-muted-foreground">
                      {notification.body.length > 400
                        ? `${notification.body.slice(0, 400)}…`
                        : notification.body}
                    </p>
                  )}
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    {relativeTime(notification.created_at)}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  {notification.link && (
                    <Link
                      href={notification.link}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      Open
                    </Link>
                  )}
                  {!notification.is_read && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => markRead.mutate(notification.id)}
                    >
                      Mark read
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
