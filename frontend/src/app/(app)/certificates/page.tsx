'use client';

import { useQuery } from '@tanstack/react-query';
import { Award, Copy, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

import {
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from '@/components/ui';
import { api, toList, type Paginated } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import type { Certificate } from '@/types';

export default function CertificatesPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['certificates'],
    queryFn: () => api.get<Paginated<Certificate>>('/certificates?page_size=50'),
  });

  const certificates = toList(data);

  return (
    <>
      <PageHeader
        title="Certificates"
        description="Every certificate carries a unique id that anyone can verify without signing in."
      />

      {isLoading && <LoadingState rows={3} />}
      {error && <ErrorState message="Certificates could not be loaded." onRetry={() => refetch()} />}
      {!isLoading && !error && certificates.length === 0 && (
        <EmptyState
          title="No certificates yet"
          description="Certificates issued to you will appear here."
        />
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {certificates.map((certificate) => (
          <Card key={certificate.id}>
            <CardContent className="pt-4 sm:pt-5">
              <div className="flex items-start gap-3">
                <span className="rounded-md bg-warning/10 p-2.5">
                  <Award className="h-5 w-5 text-warning" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={certificate.status === 'ISSUED' ? 'success' : 'danger'}>
                      {certificate.status.toLowerCase()}
                    </Badge>
                    <Badge tone="muted">{certificate.type_display}</Badge>
                  </div>
                  <h2 className="mt-1.5 font-medium">{certificate.title}</h2>
                  {certificate.description && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {certificate.description}
                    </p>
                  )}
                  <p className="mt-2 text-xs text-muted-foreground">
                    Issued {formatDate(certificate.issued_on)}
                    {certificate.department_name ? ` · ${certificate.department_name}` : ''}
                  </p>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
                <code className="rounded bg-muted px-2 py-1 font-mono text-xs">
                  {certificate.certificate_id}
                </code>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      navigator.clipboard
                        ?.writeText(certificate.certificate_id)
                        .then(() => toast.success('Certificate id copied'))
                        .catch(() => toast.error('Could not copy the id'));
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" aria-hidden />
                    Copy id
                  </Button>
                  <a
                    href={`/verify/certificate/${certificate.certificate_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/5"
                  >
                    Verify
                    <ExternalLink className="h-3 w-3" aria-hidden />
                  </a>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
