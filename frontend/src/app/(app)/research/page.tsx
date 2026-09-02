'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, FlaskConical, Plus } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { CategoryBarChart } from '@/components/charts';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  Progress,
  Select,
  StatCard,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/utils';
import type { Publication, ResearchProject } from '@/types';

export default function ResearchPage() {
  const { can } = useAuth();
  const [addingPublication, setAddingPublication] = useState(false);

  const projectsQuery = useQuery({
    queryKey: ['research-projects'],
    queryFn: () => api.get<Paginated<ResearchProject>>('/research/projects?page_size=50'),
  });

  const publicationsQuery = useQuery({
    queryKey: ['publications'],
    queryFn: () => api.get<Paginated<Publication>>('/research/publications?page_size=50'),
  });

  const statsQuery = useQuery({
    queryKey: ['publication-stats'],
    queryFn: () => api.get<any>('/research/publications/statistics'),
  });

  const projects = toList(projectsQuery.data);
  const publications = toList(publicationsQuery.data);

  return (
    <>
      <PageHeader
        title="Research"
        description="Projects, milestones and publications across the School of Public Health."
        actions={
          can('research.manage') && (
            <Button onClick={() => setAddingPublication(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              Add publication
            </Button>
          )
        }
      />

      {statsQuery.data && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Projects" value={projects.length} icon={FlaskConical} />
          <StatCard label="Publications" value={statsQuery.data.total} />
          <StatCard label="Total citations" value={statsQuery.data.total_citations} />
          <StatCard
            label="Ongoing"
            value={projects.filter((project) => project.status === 'ONGOING').length}
          />
        </div>
      )}

      <Tabs defaultValue="projects">
        <TabsList>
          <TabsTrigger value="projects">Projects ({projects.length})</TabsTrigger>
          <TabsTrigger value="publications">Publications ({publications.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="projects">
          {projectsQuery.isLoading && <LoadingState rows={3} />}
          {projectsQuery.error && (
            <ErrorState
              message="Projects could not be loaded."
              onRetry={() => projectsQuery.refetch()}
            />
          )}
          {!projectsQuery.isLoading && projects.length === 0 && (
            <EmptyState title="No research projects" description="Nothing has been registered yet." />
          )}

          <div className="space-y-3">
            {projects.map((project) => (
              <Card key={project.id}>
                <CardContent className="pt-4 sm:pt-5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h2 className="font-medium">{project.title}</h2>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {project.pi_detail?.full_name} · {project.research_area}
                      </p>
                    </div>
                    <Badge
                      tone={
                        project.status === 'ONGOING'
                          ? 'success'
                          : project.status === 'COMPLETED'
                            ? 'muted'
                            : 'warning'
                      }
                    >
                      {project.status.replace('_', ' ').toLowerCase()}
                    </Badge>
                  </div>

                  {project.abstract && (
                    <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                      {project.abstract}
                    </p>
                  )}

                  <div className="mt-3">
                    <div className="mb-1 flex items-baseline justify-between text-xs text-muted-foreground">
                      <span>Milestone progress</span>
                      <span className="tabular-nums">{project.progress}%</span>
                    </div>
                    <Progress value={project.progress} label={`${project.title} progress`} />
                  </div>

                  {project.milestones.length > 0 && (
                    <ul className="mt-3 flex flex-wrap gap-1.5">
                      {project.milestones.map((milestone) => (
                        <li key={milestone.id}>
                          <Badge
                            tone={
                              milestone.status === 'COMPLETED'
                                ? 'success'
                                : milestone.status === 'IN_PROGRESS'
                                  ? 'warning'
                                  : 'muted'
                            }
                          >
                            {milestone.title}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}

                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
                    {project.funding_agency && <span>Funded by {project.funding_agency}</span>}
                    {project.start_date && <span>From {formatDate(project.start_date)}</span>}
                    {project.ethics_approval_reference && (
                      <span>Ethics ref {project.ethics_approval_reference}</span>
                    )}
                    <span>{project.publication_count} publications</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="publications">
          {statsQuery.data?.by_year?.length > 0 && (
            <Card className="mb-4">
              <CardHeader>
                <CardTitle>Publications by year</CardTitle>
              </CardHeader>
              <CardContent>
                <CategoryBarChart
                  data={statsQuery.data.by_year}
                  xKey="year"
                  yKey="count"
                  label="Publications"
                  unit=""
                  domain={[0, Math.max(...statsQuery.data.by_year.map((r: any) => r.count)) + 1]}
                  height={200}
                />
              </CardContent>
            </Card>
          )}

          {publicationsQuery.isLoading && <LoadingState rows={3} />}
          {!publicationsQuery.isLoading && publications.length === 0 && (
            <EmptyState title="No publications recorded" />
          )}

          <div className="space-y-3">
            {publications.map((publication) => (
              <Card key={publication.id}>
                <CardContent className="pt-4 sm:pt-5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h2 className="font-medium">{publication.title}</h2>
                      <p className="mt-0.5 text-sm text-muted-foreground">{publication.authors}</p>
                      <p className="mt-1 text-sm italic text-muted-foreground">
                        {publication.venue}
                        {publication.year ? `, ${publication.year}` : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Badge tone="muted">{publication.type_display}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {publication.citation_count} citations
                      </span>
                    </div>
                  </div>

                  {publication.doi && (
                    <a
                      href={`https://doi.org/${publication.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                    >
                      {publication.doi}
                      <ExternalLink className="h-3 w-3" aria-hidden />
                    </a>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {addingPublication && <PublicationModal onClose={() => setAddingPublication(false)} />}
    </>
  );
}

function PublicationModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title: '',
    authors: '',
    venue: '',
    publication_type: 'JOURNAL',
    year: String(new Date().getFullYear()),
    doi: '',
    abstract: '',
  });

  const create = useMutation({
    mutationFn: () =>
      api.post('/research/publications', { ...form, year: Number(form.year) || null }),
    onSuccess: () => {
      toast.success('Publication added');
      queryClient.invalidateQueries({ queryKey: ['publications'] });
      queryClient.invalidateQueries({ queryKey: ['publication-stats'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The publication could not be added.');
      }
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Add a publication"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={create.isPending}
            disabled={!form.title.trim() || !form.authors.trim()}
            onClick={() => create.mutate()}
          >
            Save
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
        <Field label="Authors" required hint="Comma separated, in citation order.">
          {(props) => (
            <Input
              value={form.authors}
              onChange={(event) => setForm({ ...form, authors: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <Field label="Journal or conference">
          {(props) => (
            <Input
              value={form.venue}
              onChange={(event) => setForm({ ...form, venue: event.target.value })}
              {...props}
            />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type">
            {(props) => (
              <Select
                value={form.publication_type}
                onChange={(event) => setForm({ ...form, publication_type: event.target.value })}
                {...props}
              >
                <option value="JOURNAL">Journal article</option>
                <option value="CONFERENCE">Conference paper</option>
                <option value="BOOK">Book</option>
                <option value="CHAPTER">Book chapter</option>
                <option value="PREPRINT">Preprint</option>
                <option value="REPORT">Technical report</option>
                <option value="THESIS">Thesis</option>
              </Select>
            )}
          </Field>
          <Field label="Year">
            {(props) => (
              <Input
                type="number"
                value={form.year}
                onChange={(event) => setForm({ ...form, year: event.target.value })}
                {...props}
              />
            )}
          </Field>
        </div>
        <Field label="DOI">
          {(props) => (
            <Input
              value={form.doi}
              onChange={(event) => setForm({ ...form, doi: event.target.value })}
              placeholder="10.1016/…"
              {...props}
            />
          )}
        </Field>
        <Field label="Abstract">
          {(props) => (
            <Textarea
              value={form.abstract}
              onChange={(event) => setForm({ ...form, abstract: event.target.value })}
              rows={4}
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}
