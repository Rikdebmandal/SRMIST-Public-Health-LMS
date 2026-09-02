'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Star } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { CategoryBarChart } from '@/components/charts';
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  Modal,
  PageHeader,
  Textarea,
} from '@/components/ui';
import { ApiError, api, toList, type Paginated } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatDate } from '@/lib/utils';

interface FeedbackFormRow {
  id: string;
  title: string;
  description: string;
  form_type: string;
  is_anonymous: boolean;
  course_code?: string;
  closes_at: string | null;
  status: string;
  response_count: number;
  has_responded: boolean;
  questions: {
    id: string;
    text: string;
    question_type: string;
    choices: string[];
    scale_min: number;
    scale_max: number;
    is_required: boolean;
  }[];
}

export default function FeedbackPage() {
  const { can } = useAuth();
  const [respondingTo, setRespondingTo] = useState<FeedbackFormRow | null>(null);
  const [viewingResults, setViewingResults] = useState<FeedbackFormRow | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['feedback-forms'],
    queryFn: () => api.get<Paginated<FeedbackFormRow>>('/feedback/forms?page_size=50'),
  });

  const forms = toList(data);

  return (
    <>
      <PageHeader
        title="Feedback"
        description="Course, faculty and platform feedback. Anonymous forms never store who said what."
      />

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Feedback forms could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && forms.length === 0 && (
        <EmptyState
          title="No open forms"
          description="Feedback forms appear here while they are open."
        />
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {forms.map((form) => (
          <Card key={form.id} className="flex flex-col">
            <CardContent className="flex flex-1 flex-col pt-4 sm:pt-5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="font-medium">{form.title}</h2>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {form.form_type.toLowerCase()} feedback
                    {form.course_code ? ` · ${form.course_code}` : ''}
                  </p>
                </div>
                {form.is_anonymous && <Badge tone="muted">Anonymous</Badge>}
              </div>

              <p className="mt-2 flex-1 text-sm text-muted-foreground">{form.description}</p>

              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{form.questions.length} questions</span>
                {form.closes_at && <span>Closes {formatDate(form.closes_at)}</span>}
                {can('feedback.manage') && <span>{form.response_count} responses</span>}
              </div>

              <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-3">
                {form.has_responded ? (
                  <Badge tone="success">
                    <CheckCircle2 className="h-3 w-3" aria-hidden />
                    Submitted
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">Not yet submitted</span>
                )}
                <div className="flex gap-2">
                  {can('feedback.manage') && (
                    <Button size="sm" variant="ghost" onClick={() => setViewingResults(form)}>
                      Results
                    </Button>
                  )}
                  {!form.has_responded && can('feedback.submit') && (
                    <Button size="sm" onClick={() => setRespondingTo(form)}>
                      Respond
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {respondingTo && (
        <RespondModal form={respondingTo} onClose={() => setRespondingTo(null)} />
      )}
      {viewingResults && (
        <ResultsModal form={viewingResults} onClose={() => setViewingResults(null)} />
      )}
    </>
  );
}

function RespondModal({ form, onClose }: { form: FeedbackFormRow; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, any>>({});

  const submit = useMutation({
    mutationFn: () =>
      api.post(`/feedback/forms/${form.id}/submit`, {
        answers: form.questions.map((question) => ({
          question: question.id,
          rating_value:
            question.question_type === 'RATING' ? (answers[question.id] ?? null) : null,
          text_value: question.question_type === 'TEXT' ? (answers[question.id] ?? '') : '',
          choice_value:
            question.question_type === 'CHOICE' || question.question_type === 'YES_NO'
              ? answers[question.id]
                ? [answers[question.id]]
                : []
              : [],
        })),
      }),
    onSuccess: () => {
      toast.success('Thank you — your feedback has been recorded');
      queryClient.invalidateQueries({ queryKey: ['feedback-forms'] });
      onClose();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(error.message, {
          description: error.details ? JSON.stringify(error.details) : undefined,
        });
      } else {
        toast.error('Your response could not be submitted.');
      }
    },
  });

  const unanswered = form.questions.filter(
    (question) =>
      question.is_required &&
      (answers[question.id] === undefined || answers[question.id] === ''),
  );

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={form.title}
      description={
        form.is_anonymous
          ? 'This form is anonymous — your answers are not linked to your account.'
          : 'Your name is recorded with this response.'
      }
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={submit.isPending}
            disabled={unanswered.length > 0}
            onClick={() => submit.mutate()}
          >
            Submit feedback
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {form.is_anonymous && (
          <Alert tone="default" title="Anonymous">
            Your identity is recorded only to stop duplicate submissions — never alongside your
            answers.
          </Alert>
        )}

        {form.questions.map((question, index) => (
          <div key={question.id}>
            <p className="mb-2 text-sm font-medium">
              {index + 1}. {question.text}
              {question.is_required && <span className="ml-1 text-destructive">*</span>}
            </p>

            {question.question_type === 'RATING' && (
              <div
                role="radiogroup"
                aria-label={question.text}
                className="flex flex-wrap gap-1.5"
              >
                {Array.from(
                  { length: question.scale_max - question.scale_min + 1 },
                  (_, offset) => question.scale_min + offset,
                ).map((value) => (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={answers[question.id] === value}
                    onClick={() => setAnswers({ ...answers, [question.id]: value })}
                    className={cn(
                      'flex h-11 w-11 items-center justify-center rounded-md border text-sm font-medium transition-colors',
                      answers[question.id] === value
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border hover:bg-muted',
                    )}
                  >
                    {value}
                  </button>
                ))}
                <span className="self-center pl-2 text-xs text-muted-foreground">
                  {question.scale_min} = strongly disagree, {question.scale_max} = strongly agree
                </span>
              </div>
            )}

            {(question.question_type === 'CHOICE' || question.question_type === 'YES_NO') && (
              <div role="radiogroup" aria-label={question.text} className="flex flex-wrap gap-1.5">
                {(question.question_type === 'YES_NO' ? ['Yes', 'No'] : question.choices).map(
                  (choice) => (
                    <button
                      key={choice}
                      type="button"
                      role="radio"
                      aria-checked={answers[question.id] === choice}
                      onClick={() => setAnswers({ ...answers, [question.id]: choice })}
                      className={cn(
                        'rounded-md border px-3 py-2 text-sm transition-colors',
                        answers[question.id] === choice
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border hover:bg-muted',
                      )}
                    >
                      {choice}
                    </button>
                  ),
                )}
              </div>
            )}

            {question.question_type === 'TEXT' && (
              <Textarea
                value={answers[question.id] ?? ''}
                onChange={(event) =>
                  setAnswers({ ...answers, [question.id]: event.target.value })
                }
                rows={3}
                aria-label={question.text}
                placeholder="Your answer…"
              />
            )}
          </div>
        ))}
      </div>
    </Modal>
  );
}

function ResultsModal({ form, onClose }: { form: FeedbackFormRow; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['feedback-results', form.id],
    queryFn: () => api.get<any>(`/feedback/forms/${form.id}/results`),
  });

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Results — ${form.title}`}
      description={data ? `${data.response_count} responses` : undefined}
      footer={
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
      }
    >
      {isLoading ? (
        <LoadingState rows={4} />
      ) : data?.notice ? (
        <Alert tone="warning" title="Results withheld">
          {data.notice}
        </Alert>
      ) : (
        <div className="space-y-5">
          {data?.results?.map((result: any) => (
            <Card key={result.question_id}>
              <CardHeader>
                <CardTitle className="text-sm">{result.text}</CardTitle>
                <p className="text-xs text-muted-foreground">
                  {result.response_count} responses
                  {result.average !== undefined && ` · mean ${result.average}`}
                </p>
              </CardHeader>
              <CardContent>
                {result.distribution?.length > 0 && (
                  <CategoryBarChart
                    data={result.distribution.map((row: any) => ({
                      label: String(row.rating_value ?? row.choice),
                      count: row.count,
                    }))}
                    xKey="label"
                    yKey="count"
                    label="Responses"
                    unit=""
                    height={180}
                    domain={[0, Math.max(...result.distribution.map((r: any) => r.count)) + 1]}
                  />
                )}
                {result.responses?.length > 0 && (
                  <ul className="space-y-2">
                    {result.responses.map((text: string, index: number) => (
                      <li key={index} className="rounded-md bg-muted p-2 text-sm">
                        {text}
                      </li>
                    ))}
                  </ul>
                )}
                {!result.distribution?.length && !result.responses?.length && (
                  <p className="text-sm text-muted-foreground">No responses to this question.</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </Modal>
  );
}
