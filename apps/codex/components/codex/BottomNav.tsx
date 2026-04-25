'use client';

import { motion } from 'framer-motion';
import type { Slide } from '@/lib/slide-builder';
import { useTranslations } from '@/lib/locale-context';
import { LanguageSwitcher } from './LanguageSwitcher';

interface BottomNavProps {
  slides: Slide[];
  currentIndex: number;
  onPrev: () => void;
  onNext: () => void;
  onHome: () => void;
  onToggleSidebar: () => void;
  visitedCount: number;
  tocOpen: boolean;
  onToggleToc: () => void;
  canGoBack: boolean;
  onBack: () => void;
  explorerOpen: boolean;
  onToggleExplorer: () => void;
}

function NavIconBtn({
  icon,
  label,
  onClick,
  active = false,
  title,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
  title?: string;
}) {
  const activeColor = 'hsl(41 92% 67%)';
  const idleColor = 'rgba(255,255,255,0.45)';

  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="flex flex-col items-center justify-center rounded-lg transition-all"
      style={{
        gap: 2,
        minWidth: 44,
        padding: '6px 8px',
        color: active ? activeColor : idleColor,
        background: active ? 'rgba(247,195,93,0.10)' : 'transparent',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = active ? activeColor : 'rgba(255,255,255,0.85)';
        e.currentTarget.style.background = active
          ? 'rgba(247,195,93,0.15)'
          : 'rgba(255,255,255,0.06)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = active ? activeColor : idleColor;
        e.currentTarget.style.background = active ? 'rgba(247,195,93,0.10)' : 'transparent';
      }}
    >
      {icon}
      <span className="hidden text-[9px] font-bold tracking-wider uppercase sm:block">{label}</span>
    </button>
  );
}

export function BottomNav({
  slides,
  currentIndex,
  onPrev,
  onNext,
  onHome,
  onToggleSidebar,
  visitedCount: _visitedCount,
  tocOpen,
  onToggleToc,
  canGoBack,
  onBack,
  explorerOpen,
  onToggleExplorer,
}: BottomNavProps) {
  const t = useTranslations();
  const current = slides[currentIndex];
  const prev = slides[currentIndex - 1];
  const next = slides[currentIndex + 1];
  const progress = slides.length > 1 ? (currentIndex / (slides.length - 1)) * 100 : 0;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50"
      style={{
        height: 80,
        background: 'rgba(8,8,8,0.93)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Progress bar at top of nav */}
      <div
        className="absolute left-0 right-0 top-0"
        style={{ height: 2, background: 'rgba(255,255,255,0.06)' }}
      >
        <motion.div
          className="h-full"
          style={{
            background: 'linear-gradient(90deg, hsl(41 92% 52%), hsl(41 92% 70%))',
          }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
        />
      </div>

      <div className="flex h-full items-center px-3 sm:px-5">
        {/* Left: tool buttons */}
        <div className="flex shrink-0 items-center gap-0.5">
          <NavIconBtn
            label={t.navLessons}
            title="Lesson List (Esc)"
            active={false}
            onClick={onToggleSidebar}
            icon={
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h10" />
              </svg>
            }
          />
          <NavIconBtn
            label={t.navMap}
            title="Course Map (T)"
            active={tocOpen}
            onClick={onToggleToc}
            icon={
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <rect x="14" y="14" width="7" height="7" rx="1" />
              </svg>
            }
          />
          <NavIconBtn
            label={t.navReference}
            title="Content Reference (E)"
            active={explorerOpen}
            onClick={onToggleExplorer}
            icon={
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="11" cy="11" r="8" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35" />
              </svg>
            }
          />
          {canGoBack && (
            <NavIconBtn
              label={t.navBack}
              title="Go Back (B)"
              onClick={onBack}
              icon={
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 14l-5-5 5-5" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 9h11a5 5 0 010 10h-1" />
                </svg>
              }
            />
          )}
          <div className="ml-1 hidden sm:block">
            <LanguageSwitcher />
          </div>
        </div>

        {/* Divider */}
        <div
          className="mx-3 hidden h-8 w-px shrink-0 sm:block"
          style={{ background: 'rgba(255,255,255,0.08)' }}
        />

        {/* Prev — desktop */}
        <div className="hidden w-40 shrink-0 sm:block">
          {prev ? (
            <button
              type="button"
              onClick={onPrev}
              className="group flex max-w-full items-center gap-2 rounded-lg py-1 pr-3 text-left transition-all"
              style={{ color: 'rgba(255,255,255,0.35)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.80)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
            >
              <svg
                className="h-4 w-4 shrink-0 transition-transform group-hover:-translate-x-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              <div className="min-w-0 flex flex-col">
                <span
                  className="text-[9px] font-bold tracking-[0.15em] uppercase"
                  style={{ color: 'rgba(255,255,255,0.22)' }}
                >
                  {t.navPrevious}
                </span>
                <span className="truncate text-[12px] font-medium leading-tight">
                  {prev.shortTitle}
                </span>
              </div>
            </button>
          ) : null}
        </div>

        {/* Center: position + section */}
        <div className="flex flex-1 flex-col items-center gap-0.5">
          <div className="flex items-baseline gap-1.5">
            <span
              className="text-sm font-black"
              style={{ color: 'hsl(41 92% 67%)' }}
            >
              {currentIndex + 1}
            </span>
            <span className="text-xs text-white/20">/</span>
            <span className="text-xs font-medium text-white/40">{slides.length}</span>
          </div>
          <div
            className="max-w-[160px] truncate text-[10px] font-semibold tracking-[0.15em] uppercase"
            style={{ color: 'rgba(255,255,255,0.32)' }}
          >
            {current?.chapterTitle}
          </div>
        </div>

        {/* Next — desktop */}
        <div className="hidden w-40 shrink-0 justify-end sm:flex">
          {next ? (
            <button
              type="button"
              onClick={onNext}
              className="group flex max-w-full items-center gap-2 rounded-lg py-1 pl-3 text-right transition-all"
              style={{ color: 'rgba(255,255,255,0.35)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.80)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
            >
              <div className="min-w-0 flex flex-col items-end">
                <span
                  className="text-[9px] font-bold tracking-[0.15em] uppercase"
                  style={{ color: 'rgba(255,255,255,0.22)' }}
                >
                  {t.navNextUp}
                </span>
                <span className="truncate text-[12px] font-medium leading-tight">
                  {next.shortTitle}
                </span>
              </div>
              <svg
                className="h-4 w-4 shrink-0 transition-transform group-hover:translate-x-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          ) : (
            <button
              type="button"
              onClick={onHome}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold tracking-wider uppercase transition-all"
              style={{
                color: 'hsl(41 92% 67%)',
                border: '1px solid rgba(247,195,93,0.3)',
                background: 'rgba(247,195,93,0.08)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(247,195,93,0.15)';
                e.currentTarget.style.borderColor = 'rgba(247,195,93,0.5)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(247,195,93,0.08)';
                e.currentTarget.style.borderColor = 'rgba(247,195,93,0.3)';
              }}
            >
              {t.navStartOver}
            </button>
          )}
        </div>

        {/* Mobile: compact prev/next arrows */}
        <div className="ml-auto flex shrink-0 items-center gap-2 sm:hidden">
          <button
            type="button"
            onClick={onPrev}
            disabled={!prev}
            className="flex h-9 w-9 items-center justify-center rounded-lg transition-all"
            style={{
              color: prev ? 'rgba(255,255,255,0.65)' : 'rgba(255,255,255,0.15)',
              background: 'rgba(255,255,255,0.06)',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!next}
            className="flex h-9 w-9 items-center justify-center rounded-lg transition-all"
            style={{
              color: next ? 'rgba(255,255,255,0.65)' : 'rgba(255,255,255,0.15)',
              background: next ? 'rgba(247,195,93,0.12)' : 'rgba(255,255,255,0.06)',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
