'use client';

import { motion, AnimatePresence } from 'framer-motion';
import type { Slide } from '@/lib/slide-builder';
import { useTranslations } from '@/lib/locale-context';

interface CurriculumSidebarProps {
  open: boolean;
  slides: Slide[];
  currentIndex: number;
  visitedSlides: Set<string>;
  onNavigate: (index: number) => void;
  onClose: () => void;
}

// Group slides by chapter
function groupByChapter(slides: Slide[]) {
  const groups: { chapterIndex: number; chapterTitle: string; slides: { slide: Slide; index: number }[] }[] = [];
  const seen = new Map<number, number>(); // chapterIndex → group array index

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

export function CurriculumSidebar({
  open,
  slides,
  currentIndex,
  visitedSlides,
  onNavigate,
  onClose,
}: CurriculumSidebarProps) {
  const t = useTranslations();
  const TYPE_BADGES: Record<string, { label: string; color: string }> = {
    hero: { label: t.intro, color: 'rgba(247,195,93,0.7)' },
    'chapter-intro': { label: t.chapter, color: 'rgba(255,255,255,0.3)' },
    topic: { label: t.topicBadge, color: 'rgba(247,195,93,0.6)' },
    'case-study': { label: t.caseBadge, color: 'rgba(59,178,152,0.7)' },
    pathway: { label: t.pathBadge, color: 'rgba(147,112,200,0.7)' },
    appendix: { label: t.appxBadge, color: 'rgba(147,197,253,0.7)' },
    map: { label: t.mapBadge, color: 'rgba(96,165,250,0.7)' },
  };
  const groups = groupByChapter(slides);
  const visitedCount = visitedSlides.size;

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-30"
            style={{ background: 'rgba(0,0,0,0.4)' }}
            onClick={onClose}
          />

          {/* Sidebar */}
          <motion.div
            key="sidebar"
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="fixed bottom-0 left-0 top-0 z-40 flex flex-col overflow-hidden"
            style={{
              width: 320,
              background: 'rgba(8,8,8,0.97)',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              borderRight: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            {/* Header */}
            <div
              className="flex shrink-0 items-center justify-between px-5 py-4"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div>
                <p
                  className="text-[11px] font-black tracking-[0.28em] uppercase"
                  style={{ color: 'hsl(41 92% 67%)' }}
                >
                  Lesson List
                </p>
                <p className="text-[10px] text-white/25 mt-0.5">
                  {slides.length} slides total
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors"
                style={{ color: 'rgba(255,255,255,0.35)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.85)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
                aria-label="Close lesson list"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Slide list */}
            <div className="flex-1 overflow-y-auto py-3">
              {groups.map((group) => (
                <div key={group.chapterIndex} className="mb-4">
                  {/* Chapter header */}
                  <div className="px-5 pb-2 pt-1">
                    <span
                      className="text-[10px] font-bold tracking-[0.3em] uppercase"
                      style={{ color: 'hsl(41 92% 67% / 0.6)' }}
                    >
                      {group.chapterTitle}
                    </span>
                  </div>

                  {/* Slides in chapter */}
                  <div className="space-y-0.5 px-2">
                    {group.slides.map(({ slide, index }) => {
                      const isCurrent = index === currentIndex;
                      const isVisited = visitedSlides.has(slide.id);
                      const badge = TYPE_BADGES[slide.type] ?? TYPE_BADGES.topic;

                      return (
                        <button
                          key={slide.id}
                          type="button"
                          onClick={() => {
                            onNavigate(index);
                            onClose();
                          }}
                          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all"
                          style={{
                            background: isCurrent
                              ? 'rgba(247,195,93,0.08)'
                              : 'transparent',
                            border: isCurrent
                              ? '1px solid rgba(247,195,93,0.2)'
                              : '1px solid transparent',
                          }}
                          onMouseEnter={(e) => {
                            if (!isCurrent)
                              (e.currentTarget as HTMLButtonElement).style.background =
                                'rgba(255,255,255,0.04)';
                          }}
                          onMouseLeave={(e) => {
                            if (!isCurrent)
                              (e.currentTarget as HTMLButtonElement).style.background =
                                'transparent';
                          }}
                        >
                          {/* Status indicator */}
                          <div className="flex h-4 w-4 shrink-0 items-center justify-center">
                            {isCurrent ? (
                              <div
                                className="h-2.5 w-2.5 rounded-full"
                                style={{
                                  background: 'hsl(41 92% 67%)',
                                  boxShadow: '0 0 6px hsl(41 92% 67%)',
                                }}
                              />
                            ) : isVisited ? (
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth={2.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                            ) : (
                              <div
                                className="h-1.5 w-1.5 rounded-full"
                                style={{ background: 'rgba(255,255,255,0.15)' }}
                              />
                            )}
                          </div>

                          {/* Title */}
                          <span
                            className="flex-1 truncate text-sm"
                            style={{
                              color: isCurrent
                                ? 'hsl(41 92% 70%)'
                                : isVisited
                                ? 'rgba(255,255,255,0.6)'
                                : 'rgba(255,255,255,0.4)',
                              fontWeight: isCurrent ? 600 : 400,
                            }}
                          >
                            {slide.shortTitle}
                          </span>

                          {/* Type badge */}
                          <span
                            className="shrink-0 text-[9px] font-bold tracking-wider"
                            style={{ color: badge.color }}
                          >
                            {badge.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div
              className="shrink-0 px-5 py-4"
              style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="mb-2 flex items-center justify-between text-xs text-white/30">
                <span>Progress</span>
                <span>
                  {visitedCount} of {slides.length} slides
                </span>
              </div>
              <div
                className="h-1.5 w-full overflow-hidden rounded-full"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${(visitedCount / slides.length) * 100}%`,
                    background: 'linear-gradient(90deg, hsl(41 92% 55%), hsl(41 92% 70%))',
                  }}
                />
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
