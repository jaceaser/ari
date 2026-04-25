import Link from 'next/link';
import { AlertTriangle, GitBranch, CheckCircle2 } from 'lucide-react';
import type { Pathway } from '@/types/codex';
import type { Locale } from '@/lib/translations';

interface PathwayStepsProps {
  pathway: Pathway;
  courseSlug: string;
  locale?: Locale;
}

export function PathwaySteps({ pathway, courseSlug, locale = 'en' }: PathwayStepsProps) {
  const steps = [...pathway.steps].sort((a, b) => a.order - b.order);

  return (
    <div className="relative">
      {/* Vertical line */}
      <div
        className="absolute left-5 top-0 h-full w-px"
        style={{ backgroundColor: 'hsl(var(--ari-gold-hsl) / 0.2)' }}
      />

      <ol className="space-y-8">
        {steps.map((step, index) => (
          <li key={step.order} className="relative flex gap-6">
            {/* Step number bubble */}
            <div
              className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 text-sm font-bold"
              style={{
                borderColor: 'hsl(var(--ari-gold-hsl))',
                backgroundColor: 'hsl(var(--ari-gold-hsl) / 0.1)',
                color: 'hsl(var(--ari-gold-hsl))',
              }}
            >
              {index + 1}
            </div>

            <div className="flex-1 pb-4">
              <div className="mb-2 flex items-center gap-3">
                <h3 className="font-semibold text-[var(--foreground)]">{step.label}</h3>
                {step.topicSlug && (
                  <Link
                    href={`/${locale}/${courseSlug}/topic/${step.topicSlug}`}
                    className="inline-flex items-center gap-1 rounded-full bg-[var(--muted)] px-2.5 py-0.5 text-xs text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)]"
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    {step.topicSlug}
                  </Link>
                )}
              </div>

              {step.decisionPoints && step.decisionPoints.length > 0 && (
                <div className="mb-3 rounded-lg border border-[var(--border)] bg-[var(--muted)] p-3">
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                    <GitBranch className="h-3 w-3" /> Decision Points
                  </p>
                  <ul className="space-y-1">
                    {step.decisionPoints.map((dp, i) => (
                      <li key={i} className="text-sm text-[var(--foreground)]">
                        → {dp}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {step.risks && step.risks.length > 0 && (
                <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-400">
                    <AlertTriangle className="h-3 w-3" /> Risks
                  </p>
                  <ul className="space-y-1">
                    {step.risks.map((risk, i) => (
                      <li key={i} className="text-sm text-amber-300/80">
                        {risk}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
