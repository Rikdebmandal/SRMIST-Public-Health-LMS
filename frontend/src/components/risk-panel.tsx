'use client';

import { Info, ShieldCheck } from 'lucide-react';

import { Badge, Card, CardContent, CardHeader, CardTitle, Progress } from '@/components/ui';
import { statusTone } from '@/lib/utils';
import type { RiskOutcome } from '@/types';

/**
 * Presents the Academic Support Risk Indicator.
 *
 * Every contributing factor is shown with the observed value and the threshold
 * it crossed, so the reader can always audit the reasoning. The disclaimer is
 * not decorative — it is required by the responsible-analytics rules in the
 * brief (sections 31 and 89).
 */
export function RiskPanel({ risk, compact }: { risk?: RiskOutcome; compact?: boolean }) {
  if (!risk) return null;

  const tone = statusTone(risk.level);
  const progressTone =
    risk.level === 'critical' || risk.level === 'high'
      ? 'danger'
      : risk.level === 'moderate'
        ? 'warning'
        : 'success';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="truncate">{risk.indicator_name}</CardTitle>
            {!compact && (
              <p className="text-sm text-muted-foreground">
                A support signal, not a grade or a prediction.
              </p>
            )}
          </div>
          <Badge tone={tone} className="shrink-0">
            {risk.level_label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="text-sm text-muted-foreground">Indicator score</span>
            <span className="text-2xl font-semibold tabular-nums">{risk.score}</span>
          </div>
          <Progress value={risk.score} tone={progressTone} label="Academic support indicator" />
        </div>

        {risk.factors.length > 0 ? (
          <div className="space-y-2.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Contributing factors
            </p>
            <ul className="space-y-2.5">
              {risk.factors.map((factor) => (
                <li key={factor.code} className="rounded-md border border-border p-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">{factor.label}</p>
                    <Badge tone="muted" className="shrink-0">
                      +{factor.weight}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Observed {factor.observed}
                    {factor.metric.includes('percentage') ? '%' : ''} against a threshold of{' '}
                    {factor.threshold}
                    {factor.metric.includes('percentage') ? '%' : ''}.
                  </p>
                  {factor.guidance && (
                    <p className="mt-1 text-xs text-muted-foreground">{factor.guidance}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success/5 p-3">
            <ShieldCheck className="h-4 w-4 shrink-0 text-success" aria-hidden />
            <p className="text-sm">No support indicators are currently raised.</p>
          </div>
        )}

        <p className="flex gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {risk.disclaimer}
        </p>
      </CardContent>
    </Card>
  );
}
