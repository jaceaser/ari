'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { SerializedCourse, CodexEntity } from '@/types/codex';
import { buildSlides, type Slide } from '@/lib/slide-builder';
import { buildCrossReferenceIndex } from '@/lib/cross-reference';
import type { Locale } from '@/lib/translations';
import { getTranslations } from '@/lib/translations';
import { HeroSlide } from './slides/HeroSlide';
import { ChapterIntroSlide } from './slides/ChapterIntroSlide';
import { TopicSlide } from './slides/TopicSlide';
import { CaseStudySlide } from './slides/CaseStudySlide';
import { PathwaySlide } from './slides/PathwaySlide';
import { GlossarySlide } from './slides/GlossarySlide';
import { MapSlide } from './slides/MapSlide';
import { AppendixSlide } from './slides/AppendixSlide';
import { BottomNav } from './BottomNav';
import { CurriculumSidebar } from './CurriculumSidebar';
import { TableOfContents } from './TableOfContents';
import { ContentExplorer } from './ContentExplorer';
import { PresentationContext } from '@/contexts/PresentationContext';

const STORAGE_KEY = 'codex-visited';
const STORAGE_INDEX_KEY = 'codex-index';

const variants = {
  enter: (dir: number) => ({
    x: dir > 0 ? '100%' : '-100%',
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
    transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
  exit: (dir: number) => ({
    x: dir < 0 ? '100%' : '-100%',
    opacity: 0,
    transition: { duration: 0.4, ease: [0.55, 0.06, 0.68, 0.19] as const },
  }),
};

function renderSlide(
  slide: Slide,
  course: SerializedCourse,
  courseSlug: string,
  onStart: () => void,
  onOpenToc: () => void
) {
  const allEntities = course.allEntities as Record<string, CodexEntity>;

  switch (slide.type) {
    case 'hero':
      return <HeroSlide course={course} onStart={onStart} onOpenToc={onOpenToc} />;
    case 'chapter-intro':
      return (
        <ChapterIntroSlide
          partNumber={slide.data.partNumber}
          title={slide.data.title}
          description={slide.data.description}
          slideCount={slide.data.slideCount}
        />
      );
    case 'topic':
      return (
        <TopicSlide
          topic={slide.data.topic}
          courseSlug={courseSlug}
          slideNumber={slide.data.slideNumber}
          totalTopics={slide.data.totalTopics}
          allEntities={allEntities}
        />
      );
    case 'case-study':
      return (
        <CaseStudySlide
          caseStudy={slide.data.caseStudy}
          courseSlug={courseSlug}
          allEntities={allEntities}
        />
      );
    case 'pathway':
      return (
        <PathwaySlide
          pathway={slide.data.pathway}
          courseSlug={courseSlug}
          allEntities={allEntities}
        />
      );
    case 'glossary':
      return <GlossarySlide terms={slide.data.terms} />;
    case 'appendix':
      return <AppendixSlide courseSlug={courseSlug} sectionCount={slide.data.sectionCount} />;
    case 'map':
      return <MapSlide course={course} courseSlug={courseSlug} />;
    default:
      return null;
  }
}

interface PresentationPlayerProps {
  course: SerializedCourse;
  courseSlug: string;
  locale?: Locale;
}

export function PresentationPlayer({ course, courseSlug, locale = 'en' }: PresentationPlayerProps) {
  const t = useMemo(() => getTranslations(locale), [locale]);
  const slides = useMemo(() => buildSlides(course, t), [course, t]);
  const crossRefIndex = useMemo(() => buildCrossReferenceIndex(course), [course]);
  const [[currentIndex, direction], setSlide] = useState<[number, number]>([0, 0]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [tocOpen, setTocOpen] = useState(false);
  const [explorerOpen, setExplorerOpen] = useState(false);
  const [visitedSlides, setVisitedSlides] = useState<Set<string>>(new Set());
  const [historyStack, setHistoryStack] = useState<number[]>([]);
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  // Load persisted state from localStorage
  useEffect(() => {
    try {
      const savedVisited = localStorage.getItem(STORAGE_KEY);
      if (savedVisited) {
        setVisitedSlides(new Set(JSON.parse(savedVisited)));
      }
      const savedIndex = localStorage.getItem(STORAGE_INDEX_KEY);
      if (savedIndex) {
        const idx = parseInt(savedIndex, 10);
        if (!isNaN(idx) && idx >= 0 && idx < slides.length) {
          setSlide([idx, 0]);
        }
      }
    } catch {
      // ignore
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mark current slide as visited + persist
  useEffect(() => {
    const slide = slides[currentIndex];
    if (!slide) return;

    setVisitedSlides((prev) => {
      const next = new Set(prev);
      next.add(slide.id);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(next)));
        localStorage.setItem(STORAGE_INDEX_KEY, String(currentIndex));
      } catch {
        // ignore
      }
      return next;
    });
  }, [currentIndex, slides]);

  const paginate = useCallback(
    (newIndex: number) => {
      if (newIndex < 0 || newIndex >= slides.length) return;
      const dir = newIndex > currentIndex ? 1 : -1;
      setSlide([newIndex, dir]);
    },
    [currentIndex, slides.length]
  );

  const goNext = useCallback(() => paginate(currentIndex + 1), [currentIndex, paginate]);
  const goPrev = useCallback(() => paginate(currentIndex - 1), [currentIndex, paginate]);

  const navigateToSlug = useCallback(
    (slug: string) => {
      const targetIndex = slides.findIndex(
        (s) =>
          s.data?.topic?.slug === slug ||
          s.data?.caseStudy?.slug === slug ||
          s.data?.pathway?.slug === slug
      );
      if (targetIndex !== -1 && targetIndex !== currentIndex) {
        setHistoryStack((prev) => [...prev, currentIndex]);
        paginate(targetIndex);
      }
    },
    [slides, currentIndex, paginate]
  );

  const goBack = useCallback(() => {
    setHistoryStack((prev) => {
      if (prev.length === 0) return prev;
      const target = prev[prev.length - 1];
      paginate(target);
      return prev.slice(0, -1);
    });
  }, [paginate]);

  // Keyboard navigation
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === 'ArrowRight') goNext();
      else if (e.key === 'ArrowLeft') goPrev();
      else if (e.key === 'Escape') {
        if (explorerOpen) setExplorerOpen(false);
        else if (tocOpen) setTocOpen(false);
        else if (panelOpen) setPanelOpen(false);
        else setPanelOpen((o) => !o);
      }
      else if (e.key === 't' || e.key === 'T') setTocOpen((o) => !o);
      else if (e.key === 'e' || e.key === 'E') setExplorerOpen((o) => !o);
      else if ((e.key === 'b' || e.key === 'B') && historyStack.length > 0) goBack();
      else if (e.key === 'h' || e.key === 'H') paginate(0);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [goNext, goPrev, goBack, tocOpen, panelOpen, explorerOpen, historyStack.length]);

  // Touch swipe
  const onTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  };

  const onTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current === null || touchStartY.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    const dy = Math.abs(e.changedTouches[0].clientY - touchStartY.current);
    if (Math.abs(dx) > 50 && Math.abs(dx) > dy) {
      if (dx < 0) goNext();
      else goPrev();
    }
    touchStartX.current = null;
    touchStartY.current = null;
  };

  const currentSlide = slides[currentIndex];

  const contextValue = {
    course,
    courseSlug,
    slides,
    currentIndex,
    navigateToSlug,
    navigateToIndex: paginate,
    historyStack,
    goBack,
    crossRefIndex,
    explorerOpen,
    setExplorerOpen,
  };

  return (
    <PresentationContext.Provider value={contextValue}>
      <div
        className="fixed inset-0 overflow-hidden bg-[#080808]"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        {/* Curriculum sidebar (z-40) */}
        <CurriculumSidebar
          open={panelOpen}
          slides={slides}
          currentIndex={currentIndex}
          visitedSlides={visitedSlides}
          onNavigate={paginate}
          onClose={() => setPanelOpen(false)}
        />

        {/* Full-screen TOC overlay (z-60) */}
        <TableOfContents
          open={tocOpen}
          onClose={() => setTocOpen(false)}
          slides={slides}
          currentIndex={currentIndex}
          visitedSlides={visitedSlides}
          course={course}
          onNavigate={paginate}
        />

        {/* Content Explorer overlay (z-70) */}
        <ContentExplorer
          open={explorerOpen}
          onClose={() => setExplorerOpen(false)}
          visitedSlides={visitedSlides}
        />

        {/* Slide area — leaves 80px for bottom nav */}
        <div
          className="absolute left-0 right-0 top-0 overflow-hidden"
          style={{ bottom: 80 }}
        >
          <AnimatePresence initial={false} custom={direction} mode="popLayout">
            <motion.div
              key={currentSlide.id}
              custom={direction}
              variants={variants}
              initial="enter"
              animate="center"
              exit="exit"
              className="absolute inset-0 overflow-hidden"
            >
              {renderSlide(currentSlide, course, courseSlug, goNext, () => setTocOpen(true))}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Bottom navigation (z-50, outside AnimatePresence) */}
        <BottomNav
          slides={slides}
          currentIndex={currentIndex}
          onPrev={goPrev}
          onNext={goNext}
          onHome={() => paginate(0)}
          onToggleSidebar={() => setPanelOpen((o) => !o)}
          visitedCount={visitedSlides.size}
          tocOpen={tocOpen}
          onToggleToc={() => setTocOpen((o) => !o)}
          canGoBack={historyStack.length > 0}
          onBack={goBack}
          explorerOpen={explorerOpen}
          onToggleExplorer={() => setExplorerOpen((o) => !o)}
        />
      </div>
    </PresentationContext.Provider>
  );
}
