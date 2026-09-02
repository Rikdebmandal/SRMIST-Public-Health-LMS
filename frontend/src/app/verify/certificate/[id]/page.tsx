'use client';

/**
 * Public certificate verification — deliberately requires no sign-in and
 * exposes only what confirms authenticity (brief section 39).
 */
import { useQuery } from '@tanstack/react-query';
import { BadgeCheck, ShieldAlert, ShieldX } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

import { Badge, Card, CardContent } from '@/components/ui';
import { API_BASE } from '@/lib/api';
import { useBranding } from '@/lib/branding';
import { formatDate } from '@/lib/utils';

interface VerificationResponse {
  valid: boolean;
  message: string;
  certificate?: {
    certificate_id: string;
    holder_name: string;
    title: string;
    type_display: string;
    issued_on: string;
    valid_until: string | null;
    department: string;
    status: string;
  };
}

export default function VerifyCertificatePage() {
  const params = useParams<{ id: string }>();
  const branding = useBranding();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['verify-certificate', params.id],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/v1/verify/certificate/${params.id}`);
      return (await response.json()) as VerificationResponse;
    },
    retry: false,
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4 sm:p-8">
      <div className="w-full max-w-lg">
        <div className="mb-6 text-center">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-base font-bold text-primary-foreground">
            PH
          </span>
          <h1 className="mt-3 text-lg font-semibold">{branding.school_name}</h1>
          <p className="text-sm text-muted-foreground">{branding.institution_name}</p>
        </div>

        <Card>
          <CardContent className="pt-6">
            {isLoading && (
              <div className="flex flex-col items-center py-8" role="status">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                <p className="mt-3 text-sm text-muted-foreground">Verifying certificate…</p>
              </div>
            )}

            {!isLoading && (isError || !data) && (
              <div className="flex flex-col items-center py-8 text-center">
                <ShieldAlert className="h-10 w-10 text-warning" aria-hidden />
                <p className="mt-3 font-medium">Verification unavailable</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  The verification service could not be reached. Try again shortly.
                </p>
              </div>
            )}

            {!isLoading && data && (
              <>
                <div className="flex flex-col items-center text-center">
                  {data.valid ? (
                    <BadgeCheck className="h-12 w-12 text-success" aria-hidden />
                  ) : (
                    <ShieldX className="h-12 w-12 text-destructive" aria-hidden />
                  )}
                  <h2 className="mt-3 text-lg font-semibold">
                    {data.valid ? 'Certificate verified' : 'Not valid'}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">{data.message}</p>
                </div>

                {data.certificate && (
                  <dl className="mt-6 space-y-3 border-t border-border pt-6">
                    {[
                      ['Certificate id', data.certificate.certificate_id],
                      ['Issued to', data.certificate.holder_name],
                      ['Title', data.certificate.title],
                      ['Type', data.certificate.type_display],
                      ['Issued on', formatDate(data.certificate.issued_on)],
                      [
                        'Valid until',
                        data.certificate.valid_until
                          ? formatDate(data.certificate.valid_until)
                          : 'No expiry',
                      ],
                      ['Issuing department', data.certificate.department || '—'],
                    ].map(([label, value]) => (
                      <div key={label} className="flex flex-wrap justify-between gap-2">
                        <dt className="text-sm text-muted-foreground">{label}</dt>
                        <dd className="text-right text-sm font-medium">{value}</dd>
                      </div>
                    ))}
                    <div className="flex justify-between pt-1">
                      <dt className="text-sm text-muted-foreground">Status</dt>
                      <dd>
                        <Badge tone={data.valid ? 'success' : 'danger'}>
                          {data.certificate.status.toLowerCase()}
                        </Badge>
                      </dd>
                    </div>
                  </dl>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          {branding.footer_text}
          <br />
          <Link href="/login" className="mt-1 inline-block text-primary hover:underline">
            Sign in to the platform
          </Link>
        </p>
      </div>
    </main>
  );
}
