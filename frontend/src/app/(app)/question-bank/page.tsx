'use client';

import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { DonutChart } from '@/components/charts';
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
  StatCard,
} from '@/components/ui';
import { api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { Question } from '@/types';

const DIFFICULTY_TONE = { EASY: 'success', MEDIUM: 'warning', HARD: 'danger' } as const;

export default function QuestionBankPage() {
  const { hasRole } = useAuth();
  const isStudent = hasRole('STUDENT');
  const [term, setTerm] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [type, setType] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['questions'],
    queryFn: () => api.get<Paginated<Question>>('/questions?page_size=100'),
  });

  const statsQuery = useQuery({
    queryKey: ['question-stats'],
    queryFn: () => api.get<any>('/questions/statistics'),
  });

  const questions = toList(data);

  const filtered = useMemo(
    () =>
      questions.filter((question) => {
        const matchesTerm = !term || question.text.toLowerCase().includes(term.toLowerCase());
        const matchesDifficulty = !difficulty || question.difficulty === difficulty;
        const matchesType = !type || question.question_type === type;
        return matchesTerm && matchesDifficulty && matchesType;
      }),
    [questions, term, difficulty, type],
  );

  const types = useMemo(
    () => Array.from(new Set(questions.map((question) => question.question_type))),
    [questions],
  );

  return (
    <>
      <PageHeader
        title="Question bank"
        description={
          isStudent
            ? 'Approved practice questions for your enrolled courses.'
            : 'Reusable questions across your department, with topic and difficulty tagging.'
        }
      />

      {statsQuery.data && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total questions" value={statsQuery.data.total} />
          <StatCard
            label="Easy"
            value={
              statsQuery.data.by_difficulty?.find((row: any) => row.difficulty === 'EASY')?.count ??
              0
            }
            tone="success"
          />
          <StatCard
            label="Medium"
            value={
              statsQuery.data.by_difficulty?.find((row: any) => row.difficulty === 'MEDIUM')
                ?.count ?? 0
            }
            tone="warning"
          />
          <StatCard
            label="Hard"
            value={
              statsQuery.data.by_difficulty?.find((row: any) => row.difficulty === 'HARD')?.count ??
              0
            }
            tone="danger"
          />
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-4">
        <div className="lg:col-span-3">
          <Card className="mb-4">
            <CardContent className="flex flex-col gap-2 pt-4 sm:flex-row sm:pt-5">
              <div className="relative flex-1">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden
                />
                <Input
                  value={term}
                  onChange={(event) => setTerm(event.target.value)}
                  placeholder="Search question text"
                  aria-label="Search questions"
                  className="pl-9"
                />
              </div>
              <Select
                value={difficulty}
                onChange={(event) => setDifficulty(event.target.value)}
                aria-label="Filter by difficulty"
                className="sm:w-40"
              >
                <option value="">All difficulty</option>
                <option value="EASY">Easy</option>
                <option value="MEDIUM">Medium</option>
                <option value="HARD">Hard</option>
              </Select>
              <Select
                value={type}
                onChange={(event) => setType(event.target.value)}
                aria-label="Filter by question type"
                className="sm:w-44"
              >
                <option value="">All types</option>
                {types.map((value) => (
                  <option key={value} value={value}>
                    {value.replace('_', ' ').toLowerCase()}
                  </option>
                ))}
              </Select>
            </CardContent>
          </Card>

          {isLoading && <LoadingState rows={4} />}
          {error && (
            <ErrorState message="Questions could not be loaded." onRetry={() => refetch()} />
          )}
          {!isLoading && !error && filtered.length === 0 && (
            <EmptyState
              title="No questions match"
              description="Adjust the filters, or ask your faculty to publish questions for this course."
            />
          )}

          <div className="space-y-3">
            {filtered.map((question) => (
              <Card key={question.id}>
                <CardContent className="pt-4 sm:pt-5">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge tone="muted">{question.course_code}</Badge>
                    <Badge tone={DIFFICULTY_TONE[question.difficulty] ?? 'muted'}>
                      {question.difficulty.toLowerCase()}
                    </Badge>
                    <Badge tone="outline">{question.type_display}</Badge>
                    <span className="text-xs text-muted-foreground">{question.marks} marks</span>
                    {question.topic_name && (
                      <span className="text-xs text-muted-foreground">· {question.topic_name}</span>
                    )}
                  </div>

                  <p className="text-sm font-medium leading-relaxed">{question.text}</p>

                  {question.options.length > 0 && (
                    <ul className="mt-3 space-y-1.5">
                      {question.options.map((option, index) => (
                        <li
                          key={option.id}
                          className="flex items-start gap-2 text-sm text-muted-foreground"
                        >
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border text-xs">
                            {String.fromCharCode(65 + index)}
                          </span>
                          <span className="flex-1">{option.text}</span>
                          {!isStudent && option.is_correct && (
                            <CheckCircle2
                              className="mt-0.5 h-4 w-4 shrink-0 text-success"
                              aria-label="Correct answer"
                            />
                          )}
                        </li>
                      ))}
                    </ul>
                  )}

                  {!isStudent && question.explanation && (
                    <div className="mt-3 rounded-md bg-muted p-2.5 text-sm">
                      <p className="mb-0.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Explanation
                      </p>
                      <p className="text-muted-foreground">{question.explanation}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div className="lg:col-span-1">
          {statsQuery.data?.by_type?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>By question type</CardTitle>
              </CardHeader>
              <CardContent>
                <DonutChart
                  data={statsQuery.data.by_type.map((row: any) => ({
                    name: row.question_type.replace('_', ' ').toLowerCase(),
                    count: row.count,
                  }))}
                  nameKey="name"
                  valueKey="count"
                />
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
