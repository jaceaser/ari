'use client';

import Link from 'next/link';
import type { CourseSummary } from '@/lib/list-courses';
import type { Locale } from '@/lib/translations';
import { useTranslations } from '@/lib/locale-context';

export function CourseCard({ course, locale = 'en' }: { course: CourseSummary; locale?: Locale }) {
  const t = useTranslations();
  const stats = [
    { label: t.strategies(course.topicCount), value: course.topicCount },
    { label: t.caseStudiesCount(course.caseStudyCount), value: course.caseStudyCount },
    { label: t.pathwaysCount(course.pathwayCount), value: course.pathwayCount },
  ].filter((s) => s.value > 0);

  return (
    <Link
      href={`/${locale}/${course.slug}`}
      className="group relative flex flex-col overflow-hidden rounded-2xl transition-all duration-300"
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.07)',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLAnchorElement;
        el.style.border = '1px solid rgba(247,195,93,0.25)';
        el.style.background = 'rgba(247,195,93,0.04)';
        el.style.transform = 'translateY(-2px)';
        el.style.boxShadow = '0 8px 40px rgba(0,0,0,0.4)';
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLAnchorElement;
        el.style.border = '1px solid rgba(255,255,255,0.07)';
        el.style.background = 'rgba(255,255,255,0.03)';
        el.style.transform = 'none';
        el.style.boxShadow = 'none';
      }}
    >
      {/* Top accent line */}
      <div
        className="absolute left-0 right-0 top-0 h-[2px]"
        style={{
          background:
            'linear-gradient(90deg, transparent, hsl(41 92% 67% / 0.6), transparent)',
        }}
      />

      <div className="flex flex-1 flex-col p-7">
        <p
          className="mb-3 text-[10px] font-black tracking-[0.3em] uppercase"
          style={{ color: 'hsl(41 92% 67%)' }}
        >
          {t.interactiveCourse}
        </p>

        <h2
          className="mb-3 text-2xl font-black leading-tight tracking-tight sm:text-3xl"
          style={{
            background:
              'linear-gradient(135deg, hsl(41,92%,80%), hsl(41,92%,62%), hsl(38,85%,50%))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {course.config.title}
        </h2>

        <p className="mb-6 flex-1 text-sm text-white/50 leading-relaxed">
          {course.config.description}
        </p>

        <div className="mb-6 flex flex-wrap gap-2">
          {stats.map((s) => (
            <span
              key={s.label}
              className="rounded-full px-3 py-1 text-[11px] font-semibold"
              style={{
                color: 'rgba(247,195,93,0.80)',
                background: 'rgba(247,195,93,0.08)',
                border: '1px solid rgba(247,195,93,0.18)',
              }}
            >
              {s.label}
            </span>
          ))}
        </div>

        <div
          className="flex items-center gap-2 text-sm font-semibold"
          style={{ color: 'hsl(41 92% 67%)' }}
        >
          <span>{t.startCourse}</span>
          <svg
            className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </div>
      </div>
    </Link>
  );
}
