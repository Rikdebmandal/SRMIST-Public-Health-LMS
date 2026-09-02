'use client';

import { useMutation } from '@tanstack/react-query';
import { ArrowLeft, MailCheck } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Alert, Button, Card, CardContent, Field, Input } from '@/components/ui';
import { ApiError, api } from '@/lib/api';
import { useBranding } from '@/lib/branding';

export default function ForgotPasswordPage() {
  const branding = useBranding();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  const request = useMutation({
    mutationFn: () => api.post('/auth/password/reset', { email }, { skipRetry: true }),
    onSuccess: () => setSent(true),
    // The API answers identically whether or not the account exists, so a
    // failure here is a transport problem, not a hint about the address.
    onError: () => setSent(true),
  });

  return (
    <main className="flex min-h-screen items-center justify-center p-4 sm:p-8">
      <div className="w-full max-w-md">
        <div className="mb-6">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            PH
          </span>
          <h1 className="mt-4 text-xl font-semibold">Reset your password</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter your institutional email and we will send a reset link.
          </p>
        </div>

        <Card>
          <CardContent className="pt-5">
            {sent ? (
              <div className="text-center">
                <MailCheck className="mx-auto h-10 w-10 text-success" aria-hidden />
                <p className="mt-3 font-medium">Check your inbox</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  If an account exists for that address, a reset link is on its way. The link
                  expires in two hours.
                </p>
                <Alert tone="default" className="mt-4 text-left">
                  In this demonstration environment, email is written to the backend console rather
                  than sent.
                </Alert>
              </div>
            ) : (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  request.mutate();
                }}
                className="space-y-4"
              >
                <Field label="Email address" required>
                  {(props) => (
                    <Input
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="you@sph.srmist.demo"
                      {...props}
                    />
                  )}
                </Field>
                <Button type="submit" className="w-full" loading={request.isPending} disabled={!email}>
                  Send reset link
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <Link
          href="/login"
          className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back to sign in
        </Link>

        <p className="mt-6 text-xs text-muted-foreground">{branding.footer_text}</p>
      </div>
    </main>
  );
}
