'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { ExternalLink, Library, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import {
  Badge,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  PageHeader,
} from '@/components/ui';
import { api, toList, type Paginated } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { ResourceLink } from '@/types';

const ACCESS_TONE: Record<string, 'success' | 'warning' | 'muted' | 'default'> = {
  OPEN: 'success',
  INSTITUTIONAL: 'default',
  SUBSCRIPTION: 'warning',
  CAMPUS_ONLY: 'muted',
};

export default function LibraryPage() {
  const [term, setTerm] = useState('');
  const [category, setCategory] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['resources'],
    queryFn: () => api.get<Paginated<ResourceLink>>('/library/resources?page_size=100'),
  });

  const registerVisit = useMutation({
    mutationFn: (id: string) => api.post(`/library/resources/${id}/visit`),
  });

  const resources = toList(data);

  const categories = useMemo(
    () =>
      Array.from(
        new Set(resources.map((resource) => resource.category_name).filter(Boolean)),
      ) as string[],
    [resources],
  );

  const filtered = resources.filter((resource) => {
    const matchesTerm =
      !term ||
      resource.title.toLowerCase().includes(term.toLowerCase()) ||
      resource.description.toLowerCase().includes(term.toLowerCase());
    const matchesCategory = !category || resource.category_name === category;
    return matchesTerm && matchesCategory;
  });

  return (
    <>
      <PageHeader
        title="E-resources"
        description="Journals, databases, government portals and learning platforms for public health."
      />

      <Card className="mb-5">
        <CardContent className="pt-4 sm:pt-5">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search resources"
              aria-label="Search e-resources"
              className="pl-9"
            />
          </div>
          {categories.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setCategory('')}
                aria-pressed={category === ''}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                  category === ''
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted',
                )}
              >
                All
              </button>
              {categories.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setCategory(name)}
                  aria-pressed={category === name}
                  className={cn(
                    'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                    category === name
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted',
                  )}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Resources could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && filtered.length === 0 && (
        <EmptyState title="No resources found" description="Try a different search term." />
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((resource) => (
          <Card key={resource.id} className="flex flex-col p-4">
            <div className="flex items-start gap-2.5">
              <span className="rounded-md bg-secondary/10 p-2">
                <Library className="h-4 w-4 text-secondary" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{resource.title}</p>
                {resource.category_name && (
                  <p className="text-xs text-muted-foreground">{resource.category_name}</p>
                )}
              </div>
            </div>

            <p className="mt-2.5 flex-1 text-sm text-muted-foreground">{resource.description}</p>

            {resource.access_instructions && (
              <p className="mt-2 rounded-md bg-muted p-2 text-xs text-muted-foreground">
                {resource.access_instructions}
              </p>
            )}

            <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3">
              <Badge tone={ACCESS_TONE[resource.access_type] ?? 'muted'}>
                {resource.access_display}
              </Badge>
              <a
                href={resource.url}
                target="_blank"
                rel="noreferrer"
                onClick={() => registerVisit.mutate(resource.id)}
                className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                Open
                <ExternalLink className="h-3 w-3" aria-hidden />
              </a>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
