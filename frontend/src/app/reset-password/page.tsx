'use client';

import { useMutation } from '@tanstack/react-query';
import { CheckCircle2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';

import { Alert, Button, Card, CardContent, Field, Input } from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import { useBranding } from '@/lib/branding';

function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const branding = useBranding();
  const token = params.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = useMutation({
    mutationFn: () =>
      api.post('/auth/password/reset/confirm', { token, new_password: password }, { skipRetry: true }),
    onSuccess: () => {
      setDone(true);
      setTimeout(() => router.push('/login'), 2500);
    },
    onError: (mutationError) => {
      setError(
        mutationError instanceof ApiError
          ? [mutationError.message, ...mutationError.fieldMessages].join(' ')
          : 'The password could not be reset.',
      );
    },
  });

  const mismatch = confirm.length > 0 && password !== confirm;

  return (
    <main className="flex min-h-screen items-center justify-center p-4 sm:p-8">
      <div className="w-full max-w-md">
        <div className="mb-6">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            PH
          </span>
          <h1 className="mt-4 text-xl font-semibold">Choose a new password</h1>
        </div>

        <Card>
          <CardContent className="pt-5">
            {!token ? (
              <Alert tone="danger" title="No reset token">
                This link is incomplete. Request a new reset link from the sign-in page.
              </Alert>
            ) : done ? (
              <div className="text-center">
                <CheckCircle2 className="mx-auto h-10 w-10 text-success" aria-hidden />
                <p className="mt-3 font-medium">Password updated</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Taking you to the sign-in page…
                </p>
              </div>
            ) : (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  setError(null);
                  reset.mutate();
                }}
                className="space-y-4"
              >
                {error && (
                  <Alert tone="danger" title="Could not reset">
                    {error}
                  </Alert>
                )}
                <Field
                  label="New password"
                  required
                  hint="At least 8 characters, not entirely numeric."
                >
                  {(props) => (
                    <Input
                      type="password"
                      autoComplete="new-password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      {...props}
                    />
                  )}
                </Field>
                <Field
                  label="Confirm password"
                  required
                  error={mismatch ? 'The passwords do not match.' : undefined}
                >
                  {(props) => (
                    <Input
                      type="password"
                      autoComplete="new-password"
                      value={confirm}
                      onChange={(event) => setConfirm(event.target.value)}
                      {...props}
                    />
                  )}
                </Field>
                <Button
                  type="submit"
                  className="w-full"
                  loading={reset.isPending}
                  disabled={!password || mismatch || !confirm}
                >
                  Set new password
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <Link
          href="/login"
          className="mt-5 inline-block text-sm font-medium text-primary hover:underline"
        >
          Back to sign in
        </Link>
        <p className="mt-6 text-xs text-muted-foreground">{branding.footer_text}</p>
      </div>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center" role="status">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
