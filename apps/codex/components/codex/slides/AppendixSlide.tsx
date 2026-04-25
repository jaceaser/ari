'use client';

import Link from 'next/link';
import { useTranslations } from '@/lib/locale-context';
import { useLocale } from '@/lib/locale-context';

interface AppendixSlideProps {
  courseSlug: string;
  sectionCount: number;
}

export function AppendixSlide({ courseSlug, sectionCount }: AppendixSlideProps) {
  const t = useTranslations();
  const locale = useLocale();

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      <div className="w-full max-w-2xl text-center">
        <div
          className="mb-4 inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.2em]"
          style={{
            color: 'rgba(147,197,253,0.8)',
            borderColor: 'rgba(147,197,253,0.2)',
            background: 'rgba(59,130,246,0.08)',
          }}
        >
          {t.appendix}
        </div>

        <h1
          className="mb-4 text-4xl font-black tracking-tight sm:text-5xl"
          style={{
            background: 'linear-gradient(135deg, hsl(215, 70%, 75%), hsl(215, 60%, 55%))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {t.stateReference}
        </h1>

        <p className="mb-2 text-lg text-white/50">
          {t.appendixDescription}
        </p>
        <p className="mb-10 text-sm text-white/25">
          {t.sectionsCount(sectionCount)}
        </p>

        <Link
          href={`/${locale}/${courseSlug}/appendix`}
          className="inline-flex items-center gap-2 rounded-xl px-8 py-4 text-base font-bold transition-all"
          style={{
            background: 'rgba(59,130,246,0.15)',
            border: '1px solid rgba(147,197,253,0.3)',
            color: 'rgba(147,197,253,0.9)',
          }}
        >
          {t.openAppendix}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </Link>

        <div className="mt-8 flex flex-wrap justify-center gap-2 text-xs text-white/20">
          {[t.overview, t.fiftyStateSurvey, t.stateEntries, t.practitionerNotes].map((label) => (
            <span
              key={label}
              className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1"
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
