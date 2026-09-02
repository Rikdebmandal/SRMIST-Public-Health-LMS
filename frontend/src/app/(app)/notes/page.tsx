'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileText, Search, Upload } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

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
  Select,
  Textarea,
} from '@/components/ui';
import { ApiError, api, downloadFile, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/utils';
import type { Course, CourseSection, Note } from '@/types';

export default function NotesPage() {
  const { can } = useAuth();
  const [term, setTerm] = useState('');
  const [courseFilter, setCourseFilter] = useState('');
  const [uploading, setUploading] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['notes'],
    queryFn: () => api.get<Paginated<Note>>('/notes?page_size=100'),
  });

  const notes = toList(data);
  const courses = useMemo(
    () =>
      Array.from(new Map(notes.map((note) => [note.course, note.course_code])).entries()).sort(
        (a, b) => a[1].localeCompare(b[1]),
      ),
    [notes],
  );

  const filtered = notes.filter((note) => {
    const matchesTerm =
      !term ||
      note.title.toLowerCase().includes(term.toLowerCase()) ||
      note.topic.toLowerCase().includes(term.toLowerCase()) ||
      note.tags.some((tag) => tag.toLowerCase().includes(term.toLowerCase()));
    const matchesCourse = !courseFilter || note.course === courseFilter;
    return matchesTerm && matchesCourse;
  });

  return (
    <>
      <PageHeader
        title="Notes and resources"
        description="Lecture material, readings and supporting documents for your courses."
        actions={
          can('note.manage') && (
            <Button onClick={() => setUploading(true)}>
              <Upload className="h-4 w-4" aria-hidden />
              Upload
            </Button>
          )
        }
      />

      <Card className="mb-5">
        <CardContent className="flex flex-col gap-2 pt-4 sm:flex-row sm:pt-5">
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search by title, topic or tag"
              aria-label="Search notes"
              className="pl-9"
            />
          </div>
          <Select
            value={courseFilter}
            onChange={(event) => setCourseFilter(event.target.value)}
            aria-label="Filter by course"
            className="sm:w-56"
          >
            <option value="">All courses</option>
            {courses.map(([id, code]) => (
              <option key={id} value={id}>
                {code}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Notes could not be loaded." onRetry={() => refetch()} />}

      {!isLoading && !error && filtered.length === 0 && (
        <EmptyState
          title="No resources found"
          description={
            term || courseFilter
              ? 'Try a different search or clear the filters.'
              : 'Material uploaded by your faculty will appear here.'
          }
        />
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((note) => (
          <Card key={note.id} className="flex flex-col p-4">
            <div className="flex items-start gap-2.5">
              <span className="rounded-md bg-primary/10 p-2">
                <FileText className="h-4 w-4 text-primary" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{note.title}</p>
                <p className="text-xs text-muted-foreground">
                  {note.course_code} · {note.topic || 'General'}
                </p>
              </div>
            </div>

            {note.description && (
              <p className="mt-2.5 line-clamp-2 text-sm text-muted-foreground">
                {note.description}
              </p>
            )}

            {note.tags.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1">
                {note.tags.slice(0, 4).map((tag) => (
                  <Badge key={tag} tone="muted">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {note.active_version_detail && (
                <>
                  <span className="uppercase">{note.active_version_detail.extension}</span>
                  <span>{note.active_version_detail.size_display}</span>
                  <span>v{note.active_version_detail.version_number}</span>
                </>
              )}
              <span>{formatDate(note.created_at)}</span>
            </div>

            <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3">
              <span className="truncate text-xs text-muted-foreground">
                {note.uploaded_by || 'Faculty'}
              </span>
              {note.allow_download ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    downloadFile(
                      `/notes/${note.id}/download`,
                      note.active_version_detail?.original_filename || `${note.title}.pdf`,
                    ).catch((downloadError) =>
                      toast.error(
                        downloadError instanceof ApiError
                          ? downloadError.message
                          : 'Download failed.',
                      ),
                    )
                  }
                >
                  <Download className="h-3.5 w-3.5" aria-hidden />
                  Download
                </Button>
              ) : (
                <Badge tone="muted">View only</Badge>
              )}
            </div>
          </Card>
        ))}
      </div>

      {uploading && <UploadModal onClose={() => setUploading(false)} />}
    </>
  );
}

function UploadModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title: '',
    description: '',
    course: '',
    section: '',
    topic: '',
    tags: '',
    visibility: 'COURSE',
  });
  const [file, setFile] = useState<File | null>(null);

  const coursesQuery = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.get<Paginated<Course>>('/courses?page_size=100'),
  });

  const sectionsQuery = useQuery({
    queryKey: ['my-courses'],
    queryFn: () => api.get<CourseSection[]>('/courses/my-courses'),
  });

  const upload = useMutation({
    mutationFn: () => {
      const payload = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (value) payload.append(key, value);
      });
      if (file) payload.append('file', file);
      return api.post('/notes/upload', payload);
    },
    onSuccess: () => {
      toast.success('Resource uploaded');
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, { description: error.fieldMessages.join(' ') || undefined });
      } else {
        toast.error('The upload failed.');
      }
    },
  });

  const sectionsForCourse = (sectionsQuery.data ?? []).filter(
    (section) => !form.course || section.course === form.course,
  );

  return (
    <Modal
      open
      onClose={onClose}
      title="Upload a resource"
      description="Files are validated by extension, size and content signature before they are stored."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={upload.isPending}
            disabled={!form.title || !form.course || !file}
            onClick={() => upload.mutate()}
          >
            Upload
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

        <Field label="Course" required>
          {(props) => (
            <Select
              value={form.course}
              onChange={(event) => setForm({ ...form, course: event.target.value, section: '' })}
              {...props}
            >
              <option value="">Choose a course…</option>
              {toList(coursesQuery.data).map((course) => (
                <option key={course.id} value={course.id}>
                  {course.code} — {course.name}
                </option>
              ))}
            </Select>
          )}
        </Field>

        {sectionsForCourse.length > 0 && (
          <Field label="Section" hint="Leave empty to share with every section of the course.">
            {(props) => (
              <Select
                value={form.section}
                onChange={(event) => setForm({ ...form, section: event.target.value })}
                {...props}
              >
                <option value="">All sections</option>
                {sectionsForCourse.map((section) => (
                  <option key={section.id} value={section.id}>
                    Section {section.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Topic">
            {(props) => (
              <Input
                value={form.topic}
                onChange={(event) => setForm({ ...form, topic: event.target.value })}
                placeholder="e.g. Unit 2 — Methods"
                {...props}
              />
            )}
          </Field>
          <Field label="Tags" hint="Comma separated.">
            {(props) => (
              <Input
                value={form.tags}
                onChange={(event) => setForm({ ...form, tags: event.target.value })}
                placeholder="lecture, week3"
                {...props}
              />
            )}
          </Field>
        </div>

        <Field label="Visibility">
          {(props) => (
            <Select
              value={form.visibility}
              onChange={(event) => setForm({ ...form, visibility: event.target.value })}
              {...props}
            >
              <option value="SECTION">Enrolled students of the section</option>
              <option value="COURSE">All students of the course</option>
              <option value="DEPARTMENT">Whole department</option>
              <option value="INSTITUTION">Whole institution</option>
            </Select>
          )}
        </Field>

        <Field label="Description">
          {(props) => (
            <Textarea
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              rows={3}
              {...props}
            />
          )}
        </Field>

        <Field label="File" required hint="PDF, Office documents, images or video. Max 25 MB.">
          {(props) => (
            <Input
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              {...props}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}
