'use client';

import { useQuery } from '@tanstack/react-query';
import { BookOpen, Search, Users } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';

import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  PageHeader,
  Select,
} from '@/components/ui';
import { api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { truncate } from '@/lib/utils';
import type { Course, CourseSection } from '@/types';

export default function CoursesPage() {
  const { hasRole } = useAuth();
  const [term, setTerm] = useState('');
  const [semester, setSemester] = useState('');

  const coursesQuery = useQuery({
    queryKey: ['courses'],
    queryFn: () => api.get<Paginated<Course>>('/courses?page_size=100'),
  });

  const myQuery = useQuery({
    queryKey: ['my-courses'],
    queryFn: () => api.get<CourseSection[]>('/courses/my-courses'),
  });

  const courses = toList(coursesQuery.data);

  const filtered = useMemo(
    () =>
      courses.filter((course) => {
        const matchesTerm =
          !term ||
          course.name.toLowerCase().includes(term.toLowerCase()) ||
          course.code.toLowerCase().includes(term.toLowerCase());
        const matchesSemester = !semester || String(course.semester_number) === semester;
        return matchesTerm && matchesSemester;
      }),
    [courses, term, semester],
  );

  const semesters = useMemo(
    () => Array.from(new Set(courses.map((course) => course.semester_number))).sort(),
    [courses],
  );

  return (
    <>
      <PageHeader
        title="Courses"
        description={
          hasRole('STUDENT')
            ? 'Every course you are enrolled in this semester.'
            : 'Courses you teach or coordinate within your department.'
        }
      />

      {myQuery.data && myQuery.data.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {hasRole('STUDENT') ? 'Enrolled sections' : 'Your teaching sections'}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {myQuery.data.map((section) => (
              <Link key={section.id} href={`/courses/${section.course}`} className="group">
                <Card className="h-full p-4 transition-colors hover:border-primary/50">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-muted-foreground">
                        {section.course_code}
                      </p>
                      <p className="mt-0.5 truncate font-medium group-hover:text-primary">
                        {section.course_name}
                      </p>
                    </div>
                    <Badge tone="muted" className="shrink-0">
                      Sec {section.name}
                    </Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <BookOpen className="h-3 w-3" aria-hidden />
                      {section.course_credits} credits
                    </span>
                    <span className="flex items-center gap-1">
                      <Users className="h-3 w-3" aria-hidden />
                      {section.enrolled_count} enrolled
                    </span>
                    {section.room && <span>Room {section.room}</span>}
                  </div>
                  {section.faculty.length > 0 && (
                    <p className="mt-2 truncate text-xs text-muted-foreground">
                      {section.faculty.map((item) => item.full_name).join(', ')}
                    </p>
                  )}
                </Card>
              </Link>
            ))}
          </div>
        </section>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Course catalogue</CardTitle>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Search by code or name"
                aria-label="Search courses"
                className="pl-9"
              />
            </div>
            <Select
              value={semester}
              onChange={(event) => setSemester(event.target.value)}
              aria-label="Filter by semester"
              className="sm:w-48"
            >
              <option value="">All semesters</option>
              {semesters.map((number) => (
                <option key={number} value={number}>
                  Semester {number}
                </option>
              ))}
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {coursesQuery.isLoading && <LoadingState rows={3} />}
          {coursesQuery.error && (
            <ErrorState
              message="Courses could not be loaded."
              onRetry={() => coursesQuery.refetch()}
            />
          )}
          {!coursesQuery.isLoading && !coursesQuery.error && filtered.length === 0 && (
            <EmptyState
              title="No courses match"
              description={
                term || semester
                  ? 'Try clearing the search or semester filter.'
                  : 'No courses are visible to your account yet.'
              }
            />
          )}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((course) => (
              <Link key={course.id} href={`/courses/${course.id}`} className="group">
                <Card className="flex h-full flex-col p-4 transition-colors hover:border-primary/50">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-mono text-xs text-muted-foreground">{course.code}</p>
                    <Badge tone={course.status === 'ACTIVE' ? 'success' : 'muted'}>
                      {course.status.toLowerCase()}
                    </Badge>
                  </div>
                  <p className="mt-1 font-medium group-hover:text-primary">{course.name}</p>
                  <p className="mt-1.5 flex-1 text-sm text-muted-foreground">
                    {truncate(course.description, 110)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
                    <span>Semester {course.semester_number}</span>
                    <span>{course.credits} credits</span>
                    {course.course_type_name && <span>{course.course_type_name}</span>}
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
