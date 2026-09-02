'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { AlertCircle, Eye, EyeOff, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Alert, Badge, Button, Card, Input, Label } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useBranding } from '@/lib/branding';
import { firstName } from '@/lib/utils';

const schema = z.object({
  email: z.string().min(1, 'Enter your email address.').email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
});

type FormValues = z.infer<typeof schema>;

const DEMO_ACCOUNTS = [
  { role: 'Student', email: 'student1@sph.srmist.demo' },
  { role: 'Faculty', email: 'faculty1@sph.srmist.demo' },
  { role: 'HOD / Admin', email: 'hod@sph.srmist.demo' },
  { role: 'Dean', email: 'dean@sph.srmist.demo' },
  { role: 'Scholar', email: 'scholar1@sph.srmist.demo' },
  { role: 'Alumni', email: 'alumni1@sph.srmist.demo' },
];

export default function LoginPage() {
  const { signIn, user, loading } = useAuth();
  const branding = useBranding();
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  useEffect(() => {
    if (!loading && user) router.replace('/dashboard');
  }, [user, loading, router]);

  const onSubmit = async (values: FormValues) => {
    setFormError(null);
    try {
      const signedIn = await signIn(values.email, values.password);
      toast.success(`Welcome back, ${firstName(signedIn.full_name)}`);
      router.replace('/dashboard');
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(error.message);
      } else {
        setFormError('Could not reach the server. Check that the API is running on port 8000.');
      }
    }
  };

  const useDemo = (email: string) => {
    setValue('email', email);
    setValue('password', 'Demo@12345');
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel — hidden on small screens where it would only cost space. */}
      <div className="relative hidden flex-col justify-between bg-primary p-10 text-primary-foreground lg:flex">
        <div>
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary-foreground/15 text-lg font-bold">
            PH
          </span>
          <h1 className="mt-8 text-3xl font-semibold leading-tight">{branding.platform_name}</h1>
          <p className="mt-3 max-w-md text-primary-foreground/80">
            {branding.school_name}, {branding.institution_name}
          </p>
        </div>

        <ul className="space-y-4 text-sm text-primary-foreground/90">
          {[
            'Attendance, gradebook and assessment in one place',
            'Explainable academic support indicators for early intervention',
            'Research, alumni and mentorship built into the same platform',
          ].map((line) => (
            <li key={line} className="flex gap-3">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-foreground/70" />
              {line}
            </li>
          ))}
        </ul>

        <p className="text-xs text-primary-foreground/70">
          Academic project — M.Sc. Health Data Science. Demonstration data only.
        </p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              PH
            </span>
            <h1 className="mt-4 text-xl font-semibold">{branding.platform_name}</h1>
            <p className="text-sm text-muted-foreground">{branding.school_name}</p>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Use your institutional account to continue.
          </p>

          {formError && (
            <Alert tone="danger" className="mt-5" title="Sign-in failed">
              {formError}
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="email" required>
                Email address
              </Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                placeholder="you@sph.srmist.demo"
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? 'email-error' : undefined}
                {...register('email')}
              />
              {errors.email && (
                <p id="email-error" className="flex items-center gap-1 text-xs text-destructive">
                  <AlertCircle className="h-3 w-3" aria-hidden />
                  {errors.email.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" required>
                  Password
                </Label>
                <Link
                  href="/forgot-password"
                  className="text-xs font-medium text-primary hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="pr-10"
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden />
                  )}
                </button>
              </div>
              {errors.password && (
                <p id="password-error" className="flex items-center gap-1 text-xs text-destructive">
                  <AlertCircle className="h-3 w-3" aria-hidden />
                  {errors.password.message}
                </p>
              )}
            </div>

            <Button type="submit" className="w-full" loading={isSubmitting}>
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <Card className="mt-8 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Demonstration accounts
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Every account uses the password <code className="font-mono">Demo@12345</code>. Tap one
              to fill the form.
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => useDemo(account.email)}
                  className="rounded-full border border-border px-2.5 py-1 text-xs font-medium transition-colors hover:border-primary hover:bg-primary/5 hover:text-primary"
                >
                  {account.role}
                </button>
              ))}
            </div>
          </Card>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            {branding.footer_text}
          </p>
        </div>
      </div>
    </div>
  );
}
