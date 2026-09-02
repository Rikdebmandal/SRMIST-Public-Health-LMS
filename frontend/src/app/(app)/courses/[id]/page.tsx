'use client';

import { useQuery } from '@tanstack/react-query';
import { CalendarDays, FileText, MapPin, Users } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui';
import { api, toList, type Paginated } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { Assignment, Course, CourseSection, Note } from '@/types';

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const courseId = params.id;

  const courseQuery = useQuery({
    queryKey: ['course', courseId],
    queryFn: () => api.get<Course>(`/courses/${courseId}`),
  });

  const sectionsQuery = useQuery({
    queryKey: ['course-sections', courseId],
    queryFn: () => api.get<CourseSection[]>(`/courses/${courseId}/sections`),
    enabled: Boolean(courseId),
  });

  const notesQuery = useQuery({
    queryKey: ['course-notes', courseId],
    queryFn: () => api.get<Paginated<Note>>(`/notes?course=${courseId}`),
    enabled: Boolean(courseId),
  });

  const assignmentsQuery = useQuery({
    queryKey: ['course-assignments', courseId],
    queryFn: () => api.get<Paginated<Assignment>>('/assignments?page_size=100'),
    enabled: Boolean(courseId),
  });

  if (courseQuery.isLoading) return <LoadingState rows={4} />;
  if (courseQuery.error || !courseQuery.data) {
    return (
      <ErrorState
        title="Course unavailable"
        message="This course does not exist, or you do not have access to it."
        onRetry={() => courseQuery.refetch()}
      />
    );
  }

  const course = courseQuery.data;
  const sections = sectionsQuery.data ?? [];
  const notes = toList(notesQuery.data);
  const assignments = toList(assignmentsQuery.data).filter((item) =>
    sections.some((section) => section.id === item.section),
  );

  return (
    <>
      <PageHeader
        breadcrumbs={[{ label: 'Courses', href: '/courses' }, { label: course.code }]}
        title={course.name}
        description={`${course.code} · Semester ${course.semester_number} · ${course.credits} credits`}
        actions={
          <Badge tone={course.status === 'ACTIVE' ? 'success' : 'muted'}>
            {course.status.toLowerCase()}
          </Badge>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sections">Sections ({sections.length})</TabsTrigger>
          <TabsTrigger value="notes">Notes ({notes.length})</TabsTrigger>
          <TabsTrigger value="assignments">Assignments ({assignments.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>About this course</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm leading-relaxed">
                  {course.description || 'No description has been added.'}
                </p>
                {course.learning_outcomes?.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-semibold">Learning outcomes</h3>
                    <ul className="space-y-1.5">
                      {course.learning_outcomes.map((outcome, index) => (
                        <li key={index} className="flex gap-2 text-sm text-muted-foreground">
                          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                          {outcome}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {course.syllabus && (
                  <div>
                    <h3 className="mb-1.5 text-sm font-semibold">Syllabus</h3>
                    <p className="text-sm text-muted-foreground">{course.syllabus}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="space-y-3 text-sm">
                  {[
                    ['Code', course.code],
                    ['Department', course.department_name],
                    ['Program', course.program_name || '—'],
                    ['Type', course.course_type_name || '—'],
                    ['Credits', course.credits],
                    ['Semester', course.semester_number],
                    ['Coordinator', course.coordinator_detail?.full_name || '—'],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="flex justify-between gap-3">
                      <dt className="text-muted-foreground">{label}</dt>
                      <dd className="text-right font-medium">{value}</dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="sections">
          {sections.length === 0 ? (
            <EmptyState title="No sections" description="This course has no scheduled sections." />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {sections.map((section) => (
                <Card key={section.id} className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">Section {section.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {section.semester_name} · {section.session_name}
                      </p>
                    </div>
                    <Badge tone={section.is_active ? 'success' : 'muted'}>
                      {section.enrolled_count}/{section.capacity}
                    </Badge>
                  </div>

                  {section.faculty.length > 0 && (
                    <p className="mt-2 flex items-center gap-1.5 text-sm">
                      <Users className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
                      {section.faculty.map((item) => item.full_name).join(', ')}
                    </p>
                  )}
                  {section.room && (
                    <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5" aria-hidden />
                      {section.room}
                    </p>
                  )}
                  {section.schedule?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {section.schedule.map((slot, index) => (
                        <li
                          key={index}
                          className="flex items-center gap-1.5 text-xs text-muted-foreground"
                        >
                          <CalendarDays className="h-3 w-3" aria-hidden />
                          {slot.day} · {slot.start_time}–{slot.end_time}
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="notes">
          {notes.length === 0 ? (
            <EmptyState
              title="No notes yet"
              description="Teaching material for this course will appear here."
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {notes.map((note) => (
                <Card key={note.id} className="p-4">
                  <div className="flex items-start gap-2">
                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                    <div className="min-w-0">
                      <p className="truncate font-medium">{note.title}</p>
                      <p className="text-xs text-muted-foreground">{note.topic}</p>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {note.active_version_detail?.size_display} ·{' '}
                    {note.active_version_detail?.extension?.toUpperCase()} · v
                    {note.active_version_detail?.version_number}
                  </p>
                  <Link
                    href="/notes"
                    className="mt-3 inline-block text-sm font-medium text-primary hover:underline"
                  >
                    Open in Notes
                  </Link>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="assignments">
          {assignments.length === 0 ? (
            <EmptyState title="No assignments" description="Nothing has been set for this course." />
          ) : (
            <div className="space-y-3">
              {assignments.map((assignment) => (
                <Card key={assignment.id} className="p-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="font-medium">{assignment.title}</p>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        Due {formatDate(assignment.due_date, true)} · {assignment.max_marks} marks
                      </p>
                    </div>
                    <Badge tone={assignment.is_open ? 'success' : 'muted'} className="shrink-0">
                      {assignment.is_open ? 'Open' : 'Closed'}
                    </Badge>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}
