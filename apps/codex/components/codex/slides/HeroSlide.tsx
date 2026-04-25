'use client';

import { motion } from 'framer-motion';
import type { SerializedCourse } from '@/types/codex';
import { useTranslations } from '@/lib/locale-context';

const noiseUrl =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E";

const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.1 } },
};

const item = {
  hidden: { y: 20, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

interface PartConfig {
  part: string;
  label: string;
  count: number;
  unit: string;
  border: string;
  bg: string;
  partLabelColor: string;
  countColor: string;
  countBg: string;
}

interface HeroSlideProps {
  course: SerializedCourse;
  onStart: () => void;
  onOpenToc: () => void;
}

export function HeroSlide({ course, onStart, onOpenToc }: HeroSlideProps) {
  const t = useTranslations();
  const topicCount = course.topics.length;
  const caseCount = course.caseStudies.length;
  const pathwayCount = course.pathways.length;

  const quote = course.config.frontPageQuote;
  const attribution = course.config.frontPageQuoteAttribution;

  const parts: PartConfig[] = [
    {
      part: 'I',
      label: t.theStrategy,
      count: topicCount,
      unit: topicCount === 1 ? t.lessonSingular : t.lessonPlural,
      border: 'rgba(247,195,93,0.2)',
      bg: 'rgba(247,195,93,0.07)',
      partLabelColor: 'rgba(247,195,93,0.55)',
      countColor: 'hsl(41 92% 67%)',
      countBg: 'rgba(247,195,93,0.12)',
    },
    {
      part: 'II',
      label: t.caseStudies,
      count: caseCount,
      unit: caseCount === 1 ? t.dealSingular : t.dealPlural,
      border: 'rgba(59,178,152,0.2)',
      bg: 'rgba(59,178,152,0.07)',
      partLabelColor: 'rgba(59,178,152,0.55)',
      countColor: 'hsl(173 58% 50%)',
      countBg: 'rgba(59,178,152,0.12)',
    },
    {
      part: 'III',
      label: t.pathways,
      count: pathwayCount,
      unit: pathwayCount === 1 ? t.routeSingular : t.routePlural,
      border: 'rgba(147,112,200,0.2)',
      bg: 'rgba(147,112,200,0.07)',
      partLabelColor: 'rgba(147,112,200,0.55)',
      countColor: 'hsl(270 60% 65%)',
      countBg: 'rgba(147,112,200,0.12)',
    },
  ];

  return (
    <div
      className="relative flex h-full w-full flex-col overflow-y-auto overflow-x-hidden bg-[#080808]"
      style={{
        backgroundImage:
          'radial-gradient(ellipse 80% 55% at 50% 0%, rgba(247,195,93,0.10), transparent)',
      }}
    >
      {/* Noise texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />
      {/* Bottom vignette */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#080808] to-transparent" />

      <motion.div
        className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-10 text-center"
        variants={container}
        initial="hidden"
        animate="visible"
      >
        {/* Course type badge */}
        <motion.div variants={item} className="mb-5">
          <span
            className="inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-[11px] font-bold tracking-[0.18em] uppercase"
            style={{
              color: 'hsl(41 92% 67%)',
              borderColor: 'rgba(247,195,93,0.28)',
              background: 'rgba(247,195,93,0.07)',
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full animate-pulse"
              style={{ backgroundColor: 'hsl(41 92% 67%)', boxShadow: '0 0 6px hsl(41 92% 67%)' }}
            />
            {t.interactiveGuide}
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          variants={item}
          className="mb-4 text-[52px] font-black leading-[0.88] tracking-tight sm:text-[68px] lg:text-[84px]"
          style={{
            backgroundImage:
              'linear-gradient(135deg, hsl(41,92%,82%), hsl(41,92%,63%), hsl(38,85%,48%))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          {course.config.title.toUpperCase()}
        </motion.h1>

        {/* Description */}
        <motion.p
          variants={item}
          className="mb-7 max-w-lg text-sm text-white/50 leading-relaxed sm:text-base"
        >
          {course.config.description}
        </motion.p>

        {/* Front-page quote — rendered only when the config has it */}
        {quote && (
          <motion.blockquote
            variants={item}
            className="mb-8 max-w-xl rounded-2xl px-7 py-5 text-left"
            style={{
              background: 'rgba(247,195,93,0.05)',
              borderTop: '1px solid rgba(247,195,93,0.18)',
              borderRight: '1px solid rgba(247,195,93,0.18)',
              borderBottom: '1px solid rgba(247,195,93,0.18)',
              borderLeft: '3px solid hsl(41 92% 67% / 0.6)',
            }}
          >
            <p
              className="whitespace-pre-line text-base font-medium italic leading-relaxed sm:text-lg"
              style={{ color: 'rgba(255,255,255,0.75)' }}
            >
              {quote.trim()}
            </p>
            {attribution && (
              <footer
                className="mt-3 text-sm font-semibold tracking-wide"
                style={{ color: 'hsl(41 92% 67% / 0.7)' }}
              >
                {attribution}
              </footer>
            )}
          </motion.blockquote>
        )}

        {/* Curriculum parts */}
        <motion.div
          variants={item}
          className="mb-9 flex flex-wrap justify-center gap-2.5"
        >
          {parts.map((p) => (
            <div
              key={p.part}
              className="flex items-center gap-2 rounded-xl border px-3.5 py-2.5"
              style={{ borderColor: p.border, background: p.bg }}
            >
              <span
                className="text-[9px] font-black tracking-[0.25em] uppercase"
                style={{ color: p.partLabelColor }}
              >
                Part {p.part}
              </span>
              <span className="h-3 w-px" style={{ background: p.border }} />
              <span className="text-[13px] font-semibold text-white/70">{p.label}</span>
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                style={{ color: p.countColor, background: p.countBg }}
              >
                {p.count} {p.unit}
              </span>
            </div>
          ))}
        </motion.div>

        {/* CTA buttons — primary is large and unmissable */}
        <motion.div
          variants={item}
          className="flex flex-col items-center gap-3 sm:flex-row"
        >
          <button
            type="button"
            onClick={onStart}
            className="group relative overflow-hidden rounded-xl px-10 py-4 font-bold tracking-wider uppercase transition-all duration-300"
            style={{
              fontSize: '1.5rem',
              background: 'linear-gradient(135deg, hsl(41 92% 67%), hsl(38 85% 55%))',
              color: '#0a0a0a',
              boxShadow: '0 0 48px rgba(247,195,93,0.28), 0 4px 24px rgba(247,195,93,0.18)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow =
                '0 0 72px rgba(247,195,93,0.45), 0 6px 32px rgba(247,195,93,0.28)';
              e.currentTarget.style.transform = 'scale(1.04)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow =
                '0 0 48px rgba(247,195,93,0.28), 0 4px 24px rgba(247,195,93,0.18)';
              e.currentTarget.style.transform = 'none';
            }}
          >
            <span className="flex items-center gap-3">
              {t.press} {t.toBegin}
              <svg
                className="h-5 w-5 transition-transform group-hover:translate-x-1"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </span>
          </button>

          <button
            type="button"
            onClick={onOpenToc}
            className="flex items-center gap-2 rounded-xl border px-6 py-4 text-sm font-semibold transition-all duration-200"
            style={{
              color: 'rgba(255,255,255,0.55)',
              borderColor: 'rgba(255,255,255,0.10)',
              background: 'rgba(255,255,255,0.04)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'rgba(247,195,93,0.30)';
              e.currentTarget.style.color = 'rgba(255,255,255,0.90)';
              e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.10)';
              e.currentTarget.style.color = 'rgba(255,255,255,0.55)';
              e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
            </svg>
            {t.browseCurriculum}
          </button>
        </motion.div>

        {/* Navigation hint */}
        <motion.div
          variants={item}
          className="mt-7 flex flex-wrap items-center justify-center gap-2 text-[11px] text-white/20"
        >
          <span>Navigate with</span>
          <span className="flex items-center gap-1">
            <kbd
              className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
              style={{
                background: 'rgba(255,255,255,0.07)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'rgba(255,255,255,0.40)',
              }}
            >
              ←
            </kbd>
            <kbd
              className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
              style={{
                background: 'rgba(255,255,255,0.07)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'rgba(255,255,255,0.40)',
              }}
            >
              →
            </kbd>
          </span>
          <span>arrow keys · Swipe on mobile</span>
        </motion.div>

        <motion.p
          variants={item}
          className="mt-4 text-[11px] font-medium tracking-[0.2em] uppercase text-white/18"
        >
          {t.poweredBy}
        </motion.p>
      </motion.div>
    </div>
  );
}
