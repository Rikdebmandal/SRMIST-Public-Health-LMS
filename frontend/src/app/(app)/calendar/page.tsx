'use client';

import { useQuery } from '@tanstack/react-query';
import { CalendarDays, MapPin } from 'lucide-react';
import { useMemo, useState } from 'react';

import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from '@/components/ui';
import { api } from '@/lib/api';
import { cn, formatDate } from '@/lib/utils';
import type { CalendarItem } from '@/types';

const CATEGORY_TONE: Record<string, 'default' | 'muted' | 'success' | 'warning' | 'danger'> = {
  ACADEMIC: 'default',
  EXAMINATION: 'danger',
  ASSIGNMENT: 'warning',
  EVENT: 'success',
  SEMINAR: 'default',
  RESEARCH: 'default',
  HOLIDAY: 'muted',
  MEETING: 'muted',
  PERSONAL: 'muted',
};

const CATEGORIES = [
  'ALL',
  'ACADEMIC',
  'EXAMINATION',
  'ASSIGNMENT',
  'EVENT',
  'SEMINAR',
  'RESEARCH',
  'HOLIDAY',
];

export default function CalendarPage() {
  const [category, setCategory] = useState('ALL');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['calendar-agenda'],
    queryFn: () => api.get<{ from: string; to: string; items: CalendarItem[] }>('/events/agenda'),
  });

  const items = useMemo(
    () =>
      (data?.items ?? []).filter((item) => category === 'ALL' || item.category === category),
    [data, category],
  );

  const grouped = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    items.forEach((item) => {
      const key = item.start_at.slice(0, 10);
      map.set(key, [...(map.get(key) ?? []), item]);
    });
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [items]);

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = grouped.filter(([day]) => day >= today);
  const past = grouped.filter(([day]) => day < today).reverse();

  return (
    <>
      <PageHeader
        title="Calendar"
        description="Classes, examinations, assignment deadlines, events and holidays in one view."
      />

      <div className="mb-5 flex flex-wrap gap-1.5">
        {CATEGORIES.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setCategory(value)}
            aria-pressed={category === value}
            className={cn(
              'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
              category === value
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-muted',
            )}
          >
            {value === 'ALL' ? 'All' : value.charAt(0) + value.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {isLoading && <LoadingState rows={4} />}
      {error && <ErrorState message="The calendar could not be loaded." onRetry={() => refetch()} />}

      {!isLoading && !error && items.length === 0 && (
        <EmptyState
          title="Nothing scheduled"
          description="No entries match this filter in the current window."
        />
      )}

      {upcoming.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Upcoming
          </h2>
          <div className="space-y-4">
            {upcoming.map(([day, dayItems]) => (
              <DayGroup key={day} day={day} items={dayItems} isToday={day === today} />
            ))}
          </div>
        </section>
      )}

      {past.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Earlier
          </h2>
          <div className="space-y-4 opacity-70">
            {past.slice(0, 10).map(([day, dayItems]) => (
              <DayGroup key={day} day={day} items={dayItems} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function DayGroup({
  day,
  items,
  isToday,
}: {
  day: string;
  items: CalendarItem[];
  isToday?: boolean;
}) {
  const date = new Date(`${day}T00:00:00`);
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-lg border',
              isToday ? 'border-primary bg-primary/10 text-primary' : 'border-border',
            )}
          >
            <span className="text-[10px] font-medium uppercase">
              {date.toLocaleDateString('en-IN', { month: 'short' })}
            </span>
            <span className="text-lg font-semibold leading-none">{date.getDate()}</span>
          </div>
          <div>
            <CardTitle>
              {date.toLocaleDateString('en-IN', { weekday: 'long' })}
              {isToday && (
                <Badge tone="default" className="ml-2">
                  Today
                </Badge>
              )}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {items.length} {items.length === 1 ? 'entry' : 'entries'}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <li key={item.id} className="flex flex-wrap items-start gap-3 py-2.5 first:pt-0 last:pb-0">
              <span className="w-14 shrink-0 text-xs tabular-nums text-muted-foreground">
                {item.all_day
                  ? 'All day'
                  : new Date(item.start_at).toLocaleTimeString('en-IN', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{item.title}</p>
                {item.location && (
                  <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" aria-hidden />
                    {item.location}
                  </p>
                )}
              </div>
              <Badge tone={CATEGORY_TONE[item.category] ?? 'muted'} className="shrink-0">
                {item.category.toLowerCase()}
              </Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
