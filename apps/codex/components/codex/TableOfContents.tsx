'use client';

import { motion, AnimatePresence } from 'framer-motion';
import type { Slide } from '@/lib/slide-builder';
import type { SerializedCourse } from '@/types/codex';
import { useTranslations } from '@/lib/locale-context';

const TYPE_COLORS: Record<string, string> = {
  hero: 'hsl(41 92% 67%)',
  'chapter-intro': 'rgba(255,255,255,0.3)',
  topic: 'hsl(41 92% 67%)',
  'case-study': 'hsl(173 58% 45%)',
  pathway: 'hsl(270 60% 65%)',
  map: 'hsl(210 60% 60%)',
};

// TYPE_LABELS is now derived from translations inside the component

// Difficulty labels are now derived from translations inside the component

function groupByChapter(slides: Slide[]) {
  const groups: { chapterIndex: number; chapterTitle: string; slides: { slide: Slide; index: number }[] }[] = [];
  const seen = new Map<number, number>();

  slides.forEach((slide, index) => {
    if (!seen.has(slide.chapterIndex)) {
      seen.set(slide.chapterIndex, groups.length);
      groups.push({
        chapterIndex: slide.chapterIndex,
        chapterTitle: slide.chapterTitle,
        slides: [],
      });
    }
    const groupIdx = seen.get(slide.chapterIndex)!;
    groups[groupIdx].slides.push({ slide, index });
  });

  return groups;
}


interface TableOfContentsProps {
  open: boolean;
  onClose: () => void;
  slides: Slide[];
  currentIndex: number;
  visitedSlides: Set<string>;
  course: SerializedCourse;
  onNavigate: (index: number) => void;
}

export function TableOfContents({
  open,
  onClose,
  slides,
  currentIndex,
  visitedSlides,
  course,
  onNavigate,
}: TableOfContentsProps) {
  const t = useTranslations();
  const PART_LABELS: Record<number, string> = {
    0: t.introduction,
    1: t.partIStrategy,
    2: t.partIICaseStudies,
    3: t.partIIIPathways,
    4: t.knowledgeMap,
  };
  const DIFFICULTY_CONFIG = {
    beginner: { label: t.beginner, color: '#4ade80' },
    intermediate: { label: t.intermediate, color: '#fbbf24' },
    advanced: { label: t.advanced, color: '#f87171' },
  };
  const TYPE_LABELS: Record<string, string> = {
    hero: t.intro,
    'chapter-intro': t.chapter,
    topic: t.topicBadge,
    'case-study': t.caseStudy.toUpperCase(),
    pathway: t.pathway.toUpperCase(),
    map: t.mapBadge,
  };
  const groups = groupByChapter(slides);
  const visitedCount = visitedSlides.size;
  const progress = Math.round((visitedCount / slides.length) * 100);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="toc-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-[60] flex flex-col"
          style={{
            background: 'rgba(4,4,4,0.97)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="flex h-full flex-col"
          >
            {/* Header */}
            <div
              className="flex shrink-0 items-center justify-between px-6 py-5 sm:px-10"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="flex items-center gap-3">
                <span
                  className="text-xs font-bold tracking-[0.3em] uppercase"
                  style={{ color: 'hsl(41 92% 67%)' }}
                >
                  Course Map
                </span>
                <span className="text-xs text-white/20">·</span>
                <span className="text-xs font-medium tracking-[0.15em] uppercase text-white/40">
                  {course.config.title}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <div className="hidden items-center gap-3 sm:flex">
                  <div
                    className="h-1.5 w-32 overflow-hidden rounded-full"
                    style={{ background: 'rgba(255,255,255,0.08)' }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${progress}%`,
                        background: 'linear-gradient(90deg, hsl(41 92% 55%), hsl(41 92% 70%))',
                      }}
                    />
                  </div>
                  <span className="text-xs text-white/30">
                    {visitedCount} of {slides.length} slides
                  </span>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors"
                  style={{ color: 'rgba(255,255,255,0.4)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.9)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
                  aria-label="Close table of contents"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Title row */}
            <div className="shrink-0 px-6 pb-4 pt-5 sm:px-10">
              <h2
                className="text-2xl font-black tracking-tight sm:text-3xl"
                style={{
                  background: 'linear-gradient(135deg, hsl(41,92%,75%), hsl(41,92%,60%), hsl(38,85%,50%))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                COURSE MAP
              </h2>
              <p className="mt-1 text-sm text-white/30">
                {course.topics.length} strategies · {course.caseStudies.length} case studies · {course.pathways.length} pathways · click any card to jump
              </p>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-6 pb-24 sm:px-10">
              {groups.map((group) => {
                // Filter out hero and chapter-intro slides for the card grid
                const contentSlides = group.slides.filter(
                  ({ slide }) => slide.type !== 'hero' && slide.type !== 'chapter-intro'
                );
                const chapterSlides = group.slides;

                return (
                  <div key={group.chapterIndex} className="mb-10">
                    {/* Chapter label with divider */}
                    <div className="mb-4 flex items-center gap-4">
                      <span
                        className="shrink-0 text-[11px] font-black tracking-[0.25em] uppercase"
                        style={{ color: 'hsl(41 92% 67% / 0.7)' }}
                      >
                        {PART_LABELS[group.chapterIndex] ?? group.chapterTitle.toUpperCase()}
                      </span>
                      <div
                        className="h-px flex-1"
                        style={{ background: 'rgba(247,195,93,0.1)' }}
                      />
                    </div>

                    {/* Chapter-intro & hero as standalone row buttons */}
                    {chapterSlides
                      .filter(({ slide }) => slide.type === 'hero' || slide.type === 'chapter-intro')
                      .map(({ slide, index }) => {
                        const isCurrent = index === currentIndex;
                        const isVisited = visitedSlides.has(slide.id);
                        return (
                          <button
                            key={slide.id}
                            type="button"
                            onClick={() => { onNavigate(index); onClose(); }}
                            className="mb-3 flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-all duration-200"
                            style={{
                              background: isCurrent ? 'rgba(247,195,93,0.08)' : 'rgba(255,255,255,0.02)',
                              border: isCurrent ? '1px solid rgba(247,195,93,0.3)' : '1px solid rgba(255,255,255,0.05)',
                            }}
                            onMouseEnter={(e) => {
                              if (!isCurrent) e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                            }}
                            onMouseLeave={(e) => {
                              if (!isCurrent) e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                            }}
                          >
                            <StatusDot isCurrent={isCurrent} isVisited={isVisited} />
                            <span
                              className="flex-1 text-sm font-medium"
                              style={{ color: isCurrent ? 'hsl(41 92% 70%)' : 'rgba(255,255,255,0.5)' }}
                            >
                              {slide.shortTitle}
                            </span>
                            <span
                              className="text-[9px] font-bold tracking-wider uppercase"
                              style={{ color: TYPE_COLORS[slide.type] ?? 'rgba(255,255,255,0.3)' }}
                            >
                              {TYPE_LABELS[slide.type]}
                            </span>
                          </button>
                        );
                      })}

                    {/* Content slide cards in grid */}
                    {contentSlides.length > 0 && (
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {contentSlides.map(({ slide, index }) => {
                          const isCurrent = index === currentIndex;
                          const isVisited = visitedSlides.has(slide.id);
                          const typeColor = TYPE_COLORS[slide.type] ?? TYPE_COLORS.topic;
                          const typeLabel = TYPE_LABELS[slide.type] ?? 'SLIDE';

                          // Pull entity data for rich display
                          const topic = slide.type === 'topic' ? slide.data?.topic : null;
                          const caseStudy = slide.type === 'case-study' ? slide.data?.caseStudy : null;
                          const pathway = slide.type === 'pathway' ? slide.data?.pathway : null;
                          const entity = topic ?? caseStudy ?? pathway;

                          const difficulty = topic
                            ? DIFFICULTY_CONFIG[topic.difficultyLevel as keyof typeof DIFFICULTY_CONFIG]
                            : null;

                          return (
                            <button
                              key={slide.id}
                              type="button"
                              onClick={() => { onNavigate(index); onClose(); }}
                              className="group flex flex-col rounded-2xl p-4 text-left transition-all duration-200"
                              style={{
                                background: isCurrent ? `${typeColor}10` : 'rgba(255,255,255,0.02)',
                                border: isCurrent
                                  ? `1px solid ${typeColor}50`
                                  : '1px solid rgba(255,255,255,0.06)',
                                boxShadow: isCurrent ? `0 0 20px ${typeColor}15` : 'none',
                              }}
                              onMouseEnter={(e) => {
                                if (!isCurrent) {
                                  e.currentTarget.style.background = `${typeColor}08`;
                                  e.currentTarget.style.borderColor = `${typeColor}30`;
                                  e.currentTarget.style.transform = 'translateY(-2px)';
                                  e.currentTarget.style.boxShadow = `0 4px 20px rgba(0,0,0,0.3)`;
                                }
                              }}
                              onMouseLeave={(e) => {
                                if (!isCurrent) {
                                  e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                                  e.currentTarget.style.transform = 'none';
                                  e.currentTarget.style.boxShadow = 'none';
                                }
                              }}
                            >
                              {/* Top row: type badge + visited indicator */}
                              <div className="mb-2 flex items-center justify-between">
                                <span
                                  className="text-[9px] font-bold tracking-[0.2em] uppercase"
                                  style={{ color: typeColor }}
                                >
                                  {typeLabel}
                                </span>
                                <StatusDot isCurrent={isCurrent} isVisited={isVisited} />
                              </div>

                              {/* Title */}
                              <p
                                className="mb-1.5 text-sm font-bold leading-snug"
                                style={{
                                  color: isCurrent ? 'hsl(41 92% 75%)' : 'rgba(255,255,255,0.85)',
                                }}
                              >
                                {slide.shortTitle}
                              </p>

                              {/* Summary */}
                              {entity?.summary && (
                                <p className="mb-2 text-[11px] text-white/40 leading-relaxed line-clamp-2">
                                  {entity.summary}
                                </p>
                              )}

                              {/* Bottom meta */}
                              <div className="mt-auto pt-2 flex items-center gap-2 flex-wrap">
                                {difficulty && (
                                  <span
                                    className="text-[9px] font-semibold"
                                    style={{ color: difficulty.color }}
                                  >
                                    {difficulty.label}
                                  </span>
                                )}
                                {caseStudy?.scenario && (
                                  <span className="text-[10px] text-white/25 line-clamp-1 flex-1">
                                    {caseStudy.scenario.slice(0, 60)}…
                                  </span>
                                )}
                                {pathway?.entryCondition && (
                                  <span className="text-[10px] text-white/25 line-clamp-1 flex-1">
                                    Entry: {pathway.entryCondition.slice(0, 50)}…
                                  </span>
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Footer progress bar */}
            <div
              className="fixed bottom-0 left-0 right-0 flex items-center gap-4 px-6 py-4 sm:px-10"
              style={{
                background: 'rgba(4,4,4,0.95)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                borderTop: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <span className="text-xs text-white/30">
                {visitedCount} / {slides.length} slides completed
              </span>
              <div
                className="flex-1 h-1.5 overflow-hidden rounded-full"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${progress}%`,
                    background: 'linear-gradient(90deg, hsl(41 92% 55%), hsl(41 92% 70%))',
                  }}
                />
              </div>
              <span
                className="text-xs font-bold"
                style={{ color: 'hsl(41 92% 67%)' }}
              >
                {progress}%
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function StatusDot({
  isCurrent,
  isVisited,
}: {
  isCurrent: boolean;
  isVisited: boolean;
}) {
  if (isCurrent) {
    return (
      <div
        className="h-3 w-3 rounded-full shrink-0"
        style={{
          background: 'hsl(41 92% 67%)',
          boxShadow: '0 0 8px hsl(41 92% 67%)',
          border: '2px solid hsl(41 92% 80%)',
        }}
      />
    );
  }
  if (isVisited) {
    return (
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="hsl(41 92% 67%)" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    );
  }
  return (
    <div
      className="h-2 w-2 rounded-full shrink-0"
      style={{ background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.2)' }}
    />
  );
}
