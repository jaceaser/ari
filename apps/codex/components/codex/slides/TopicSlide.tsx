'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';
import type { Topic, CodexEntity } from '@/types/codex';
import { CodexLink } from '../CodexLink';
import { useTranslations } from '@/lib/locale-context';

const noiseUrl =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E";

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07, delayChildren: 0.15 } },
};

const itemVariants = {
  hidden: { y: 20, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.48, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

const DIFFICULTY_COLORS = {
  beginner: { color: '#4ade80', bg: 'rgba(74,222,128,0.10)', border: 'rgba(74,222,128,0.28)' },
  intermediate: { color: '#fbbf24', bg: 'rgba(251,191,36,0.10)', border: 'rgba(251,191,36,0.28)' },
  advanced: { color: '#f87171', bg: 'rgba(248,113,113,0.10)', border: 'rgba(248,113,113,0.28)' },
};

type TabId = 'overview' | 'risks' | 'related';

interface TopicSlideProps {
  topic: Topic;
  courseSlug: string;
  slideNumber: number;
  totalTopics: number;
  allEntities: Record<string, CodexEntity>;
}

export function TopicSlide({
  topic,
  slideNumber,
  totalTopics,
}: TopicSlideProps) {
  const t = useTranslations();
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  const difficultyLabels = {
    beginner: t.beginner,
    intermediate: t.intermediate,
    advanced: t.advanced,
  };
  const difficultyColors = DIFFICULTY_COLORS[topic.difficultyLevel] ?? DIFFICULTY_COLORS.intermediate;
  const difficultyLabel = difficultyLabels[topic.difficultyLevel] ?? t.intermediate;

  const TABS: { id: TabId; label: string; shortLabel: string }[] = [
    { id: 'overview', label: t.tabOverview, shortLabel: t.tabOverview },
    { id: 'risks', label: t.tabRisks, shortLabel: t.tabRisksShort },
    { id: 'related', label: t.tabRelated, shortLabel: t.tabRelated },
  ];

  const relatedSlugs = [
    ...(topic.relatedNodes ?? []),
    ...(topic.prerequisites ?? []),
    ...(topic.nextSteps ?? []),
  ].filter(Boolean);

  return (
    <div className="relative flex h-full w-full overflow-hidden bg-[#080808]">
      {/* Noise texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />

      {/* Background accent */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 45% 55% at 95% 50%, rgba(247,195,93,0.04), transparent)',
        }}
      />

      {/* Main layout: content area left, meta rail right */}
      <div className="relative z-10 flex h-full w-full">
        {/* LEFT — scrollable content */}
        <motion.div
          className="flex h-full flex-col justify-start overflow-y-auto px-8 py-7 md:px-10 lg:w-[62%]"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          key={topic.slug}
        >
          {/* Lesson breadcrumb */}
          <motion.div variants={itemVariants} className="mb-3 flex items-center gap-2.5">
            <span
              className="text-[11px] font-black tracking-[0.28em] uppercase"
              style={{ color: 'hsl(41 92% 67%)' }}
            >
              Concept
            </span>
            <span className="text-[11px] text-white/20">·</span>
            <span className="text-[11px] font-semibold text-white/35">
              {slideNumber} of {totalTopics}
            </span>
            <span
              className="ml-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold"
              style={{
                color: difficultyColors.color,
                background: difficultyColors.bg,
                border: `1px solid ${difficultyColors.border}`,
              }}
            >
              {difficultyLabel}
            </span>
            {topic.estimatedReadTime && (
              <span className="flex items-center gap-1 text-[10px] text-white/28">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                {topic.estimatedReadTime} min
              </span>
            )}
          </motion.div>

          {/* Title */}
          <motion.h1
            variants={itemVariants}
            className="mb-5 text-[36px] font-black leading-[0.92] tracking-tight sm:text-[44px] lg:text-[52px]"
            style={{
              background:
                'linear-gradient(135deg, hsl(41,92%,78%), hsl(41,92%,62%), hsl(38,85%,50%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            {topic.title}
          </motion.h1>

          {/* Tab bar */}
          <motion.div variants={itemVariants} className="mb-5 flex gap-1.5">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className="rounded-lg px-4 py-2 text-xs font-semibold transition-all duration-200"
                style={{
                  color: activeTab === tab.id ? '#080808' : 'rgba(255,255,255,0.45)',
                  background:
                    activeTab === tab.id
                      ? 'hsl(41 92% 67%)'
                      : 'rgba(255,255,255,0.05)',
                  border: activeTab === tab.id
                    ? '1px solid transparent'
                    : '1px solid rgba(255,255,255,0.08)',
                }}
                onMouseEnter={(e) => {
                  if (activeTab !== tab.id) {
                    e.currentTarget.style.color = 'rgba(255,255,255,0.80)';
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (activeTab !== tab.id) {
                    e.currentTarget.style.color = 'rgba(255,255,255,0.45)';
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                  }
                }}
              >
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.shortLabel}</span>
              </button>
            ))}
          </motion.div>

          {/* Tab content */}
          <motion.div variants={itemVariants} className="flex-1 pb-4">
            {activeTab === 'overview' && (
              <div className="space-y-4">
                {/* Plain English callout */}
                {topic.plainEnglish && (
                  <div
                    className="rounded-2xl p-5"
                    style={{
                      background: 'rgba(247,195,93,0.05)',
                      border: '1px solid rgba(247,195,93,0.18)',
                      borderLeft: '3px solid hsl(41 92% 67% / 0.7)',
                    }}
                  >
                    <p className="text-base text-white/85 leading-relaxed italic">
                      &ldquo;{topic.plainEnglish}&rdquo;
                    </p>
                  </div>
                )}

                {/* Why / When grid */}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {topic.whyItMatters && (
                    <div
                      className="rounded-xl p-4"
                      style={{
                        background: 'rgba(255,255,255,0.035)',
                        border: '1px solid rgba(255,255,255,0.07)',
                      }}
                    >
                      <p className="mb-2 text-[11px] font-bold tracking-[0.18em] uppercase"
                        style={{ color: 'rgba(255,255,255,0.38)' }}>
                        {t.whyItMatters}
                      </p>
                      <p className="text-sm text-white/70 leading-relaxed line-clamp-5">
                        {topic.whyItMatters}
                      </p>
                    </div>
                  )}
                  {topic.whenUsed && (
                    <div
                      className="rounded-xl p-4"
                      style={{
                        background: 'rgba(255,255,255,0.035)',
                        border: '1px solid rgba(255,255,255,0.07)',
                      }}
                    >
                      <p className="mb-2 text-[11px] font-bold tracking-[0.18em] uppercase"
                        style={{ color: 'rgba(255,255,255,0.38)' }}>
                        When To Use
                      </p>
                      <p className="text-sm text-white/70 leading-relaxed line-clamp-5">
                        {topic.whenUsed}
                      </p>
                    </div>
                  )}
                </div>

                {/* Operator notes */}
                {topic.operatorNotes && (
                  <div
                    className="rounded-xl p-4"
                    style={{
                      background: 'rgba(255,255,255,0.025)',
                      border: '1px solid rgba(255,255,255,0.06)',
                    }}
                  >
                    <p className="mb-2 flex items-center gap-2 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                      </svg>
                      {t.operatorNotes}
                    </p>
                    <p className="text-sm text-white/65 leading-relaxed">{topic.operatorNotes}</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'risks' && (
              <div className="space-y-5">
                {topic.risks && topic.risks.length > 0 && (
                  <div>
                    <p className="mb-3 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      {t.risksLabel}
                    </p>
                    <div className="space-y-2">
                      {topic.risks.map((risk, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-3 rounded-xl p-3.5"
                          style={{
                            background: 'rgba(248,113,113,0.07)',
                            border: '1px solid rgba(248,113,113,0.18)',
                          }}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="#fca5a5" className="mt-0.5 shrink-0">
                            <path d="M12 2L1 21h22L12 2zm1 14h-2v-2h2v2zm0-4h-2V8h2v4z" />
                          </svg>
                          <p className="text-sm text-white/70 leading-relaxed">{risk}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {topic.applicabilitySignals && topic.applicabilitySignals.length > 0 && (
                  <div>
                    <p className="mb-3 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      Green Lights — When to proceed
                    </p>
                    <div className="space-y-2">
                      {topic.applicabilitySignals.map((signal, i) => (
                        <div key={i} className="flex items-center gap-2.5 text-sm text-white/70">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth={2.5} className="shrink-0">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                          {signal}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {topic.disqualifiers && topic.disqualifiers.length > 0 && (
                  <div>
                    <p className="mb-3 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      {t.disqualifiers}
                    </p>
                    <div className="space-y-2">
                      {topic.disqualifiers.map((d, i) => (
                        <div key={i} className="flex items-center gap-2.5 text-sm text-white/70">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth={2.5} className="shrink-0">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          {d}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'related' && (
              <div className="space-y-5">
                {topic.prerequisites && topic.prerequisites.length > 0 && (
                  <div>
                    <p className="mb-3 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      Prerequisites — Learn these first
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {topic.prerequisites.map((slug) => (
                        <CodexLink key={slug} slug={slug} variant="chip" />
                      ))}
                    </div>
                  </div>
                )}

                {topic.relatedNodes && topic.relatedNodes.length > 0 && (
                  <div>
                    <p className="mb-3 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      {t.relatedConcepts}
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {topic.relatedNodes.map((slug) => (
                        <CodexLink key={slug} slug={slug} variant="card" />
                      ))}
                    </div>
                  </div>
                )}

                {topic.nextSteps && topic.nextSteps.length > 0 && (
                  <div>
                    <p className="mb-3 text-[11px] font-bold tracking-[0.18em] uppercase"
                      style={{ color: 'rgba(255,255,255,0.35)' }}>
                      {t.nextStepsLabel}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {topic.nextSteps.map((slug) => (
                        <CodexLink key={slug} slug={slug} variant="chip">
                          <span className="flex items-center gap-1">
                            {slug}
                            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                            </svg>
                          </span>
                        </CodexLink>
                      ))}
                    </div>
                  </div>
                )}

                {relatedSlugs.length === 0 && (
                  <p className="text-sm text-white/25 italic">{t.noRelatedContent}</p>
                )}
              </div>
            )}
          </motion.div>
        </motion.div>

        {/* RIGHT META RAIL — hidden on mobile, narrow on desktop */}
        <motion.div
          className="hidden h-full flex-col gap-4 border-l px-6 py-7 md:flex lg:w-[38%]"
          style={{ borderColor: 'rgba(255,255,255,0.05)', overflowY: 'auto' }}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          {/* Difficulty + read time row */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <span
              className="rounded-lg px-3 py-1.5 text-xs font-bold tracking-wide"
              style={{
                color: difficultyColors.color,
                background: difficultyColors.bg,
                border: `1px solid ${difficultyColors.border}`,
              }}
            >
              {difficultyLabel}
            </span>
            {topic.estimatedReadTime && (
              <span className="flex items-center gap-1.5 text-xs"
                style={{ color: 'rgba(255,255,255,0.35)' }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                {topic.estimatedReadTime} {t.minRead}
              </span>
            )}
          </div>

          {/* Applicability signals (compact) */}
          {topic.applicabilitySignals && topic.applicabilitySignals.length > 0 && (
            <div
              className="rounded-xl p-4"
              style={{
                background: 'rgba(74,222,128,0.05)',
                border: '1px solid rgba(74,222,128,0.15)',
              }}
            >
              <p className="mb-2.5 text-[10px] font-bold tracking-[0.2em] uppercase"
                style={{ color: 'rgba(74,222,128,0.6)' }}>
                {t.lookForSignals}
              </p>
              <div className="flex flex-col gap-1.5">
                {topic.applicabilitySignals.slice(0, 6).map((signal, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-white/60">
                    <span className="h-1 w-1 shrink-0 rounded-full" style={{ background: '#4ade80' }} />
                    {signal}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tags */}
          {topic.tags && topic.tags.length > 0 && (
            <div>
              <p className="mb-2 text-[10px] font-bold tracking-[0.2em] uppercase"
                style={{ color: 'rgba(255,255,255,0.22)' }}>
                Tags
              </p>
              <div className="flex flex-wrap gap-1.5">
                {topic.tags.slice(0, 8).map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full px-2.5 py-0.5 text-[11px]"
                    style={{
                      color: 'rgba(255,255,255,0.45)',
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Next steps (compact) */}
          {topic.nextSteps && topic.nextSteps.length > 0 && (
            <div>
              <p className="mb-2 text-[10px] font-bold tracking-[0.2em] uppercase"
                style={{ color: 'rgba(255,255,255,0.22)' }}>
                After this
              </p>
              <div className="flex flex-col gap-1">
                {topic.nextSteps.slice(0, 4).map((slug) => (
                  <CodexLink key={slug} slug={slug} variant="chip" />
                ))}
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
