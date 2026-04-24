'use client';
import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { usePresentation } from '@/contexts/PresentationContext';
import type { CrossRef } from '@/lib/cross-reference';

const TYPE_COLORS: Record<string, string> = {
  topic: 'hsl(41 92% 67%)',
  'case-study': 'hsl(173 58% 45%)',
  pathway: 'hsl(270 60% 65%)',
  'operator-card': 'hsl(25 90% 60%)',
  glossary: 'hsl(210 60% 60%)',
};

interface TooltipPortalProps {
  visible: boolean;
  x: number;
  y: number;
  color: string;
  entity: { type: string; title: string; summary?: string };
  refs: CrossRef[];
  onNavigate: (slug: string) => void;
  onNavigateToEntity: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

function TooltipPortal({
  visible,
  x,
  y,
  color,
  entity,
  refs,
  onNavigate,
  onNavigateToEntity,
  onMouseEnter,
  onMouseLeave,
}: TooltipPortalProps) {
  if (typeof document === 'undefined') return null;

  const displayRefs = refs.slice(0, 3);
  const extraCount = refs.length - displayRefs.length;

  return createPortal(
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.95 }}
          transition={{ duration: 0.15 }}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          className="w-64 rounded-xl p-3 text-left"
          style={{
            position: 'fixed',
            left: x,
            top: y - 8,
            transform: 'translate(-50%, -100%)',
            background: 'rgba(12,12,12,0.97)',
            border: `1px solid ${color}30`,
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            boxShadow: `0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px ${color}15`,
            zIndex: 9999,
            pointerEvents: 'auto',
          }}
        >
          {/* Type badge + title */}
          <p className="mb-0.5 text-[9px] font-bold tracking-[0.2em] uppercase" style={{ color }}>
            {entity.type.replace('-', ' ')}
          </p>
          <p className="mb-1 text-xs font-semibold" style={{ color: 'rgba(255,255,255,0.90)' }}>
            {entity.title}
          </p>
          {entity.summary && (
            <p
              className="text-[11px] leading-relaxed line-clamp-2"
              style={{ color: 'rgba(255,255,255,0.50)' }}
            >
              {entity.summary}
            </p>
          )}

          {/* Cross-references */}
          {refs.length > 0 && (
            <>
              <div
                className="my-2 h-px"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              />
              <p
                className="mb-1.5 text-[9px] font-bold uppercase tracking-[0.18em]"
                style={{ color: 'rgba(255,255,255,0.35)' }}
              >
                Referenced in {refs.length} place{refs.length !== 1 ? 's' : ''}
              </p>
              <div className="space-y-1">
                {displayRefs.map((ref, i) => {
                  const refColor = TYPE_COLORS[ref.sourceType] ?? TYPE_COLORS.topic;
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onNavigate(ref.sourceSlug);
                      }}
                      className="flex w-full items-start gap-1.5 rounded px-1.5 py-1 text-left transition-all"
                      style={{ background: 'transparent' }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = `${refColor}12`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      <span
                        className="mt-0.5 text-[9px] font-bold uppercase tracking-wider shrink-0"
                        style={{ color: refColor }}
                      >
                        →
                      </span>
                      <div className="min-w-0">
                        <span
                          className="block truncate text-[11px] font-semibold"
                          style={{ color: refColor }}
                        >
                          {ref.sourceTitle}
                        </span>
                        <span
                          className="block truncate text-[10px]"
                          style={{ color: 'rgba(255,255,255,0.35)' }}
                        >
                          {ref.context}
                        </span>
                      </div>
                    </button>
                  );
                })}
                {extraCount > 0 && (
                  <p
                    className="pl-1.5 text-[10px]"
                    style={{ color: 'rgba(255,255,255,0.25)' }}
                  >
                    + {extraCount} more
                  </p>
                )}
              </div>
            </>
          )}

          {/* Navigate button */}
          <div
            className="mt-2 h-px"
            style={{ background: 'rgba(255,255,255,0.08)' }}
          />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onNavigateToEntity();
            }}
            className="mt-2 flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs font-semibold transition-all"
            style={{
              background: `${color}10`,
              border: `1px solid ${color}25`,
              color,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = `${color}20`;
              e.currentTarget.style.borderColor = `${color}45`;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = `${color}10`;
              e.currentTarget.style.borderColor = `${color}25`;
            }}
          >
            <span>Go to {entity.title}</span>
            <span>→</span>
          </button>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

interface CodexLinkProps {
  slug: string;
  children?: React.ReactNode;
  variant?: 'chip' | 'inline' | 'card';
}

export function CodexLink({ slug, children, variant = 'chip' }: CodexLinkProps) {
  const { navigateToSlug, course, crossRefIndex } = usePresentation();
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const hideTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const btnRef = useRef<HTMLButtonElement>(null);

  const entity = course.allEntities[slug];
  if (!entity) return <>{children}</>;

  const color = TYPE_COLORS[entity.type] ?? TYPE_COLORS.topic;
  const label = children ?? entity.title;
  const refs = crossRefIndex[slug] ?? [];

  const showTooltip = useCallback(() => {
    clearTimeout(hideTimeout.current);
    const rect = btnRef.current?.getBoundingClientRect();
    if (rect) {
      setTooltipPos({ x: rect.left + rect.width / 2, y: rect.top });
    }
    setTooltipVisible(true);
  }, []);

  const scheduleHide = useCallback(() => {
    hideTimeout.current = setTimeout(() => setTooltipVisible(false), 150);
  }, []);

  const handleMouseEnter = useCallback(() => {
    clearTimeout(hideTimeout.current);
    const rect = btnRef.current?.getBoundingClientRect();
    if (rect) {
      setTooltipPos({ x: rect.left + rect.width / 2, y: rect.top });
    }
    hideTimeout.current = setTimeout(() => setTooltipVisible(true), 250);
  }, []);

  const handleNavigateToEntity = useCallback(() => {
    setTooltipVisible(false);
    navigateToSlug(slug);
  }, [navigateToSlug, slug]);

  const handleNavigateToRef = useCallback(
    (refSlug: string) => {
      setTooltipVisible(false);
      navigateToSlug(refSlug);
    },
    [navigateToSlug]
  );

  const tooltipPortal = (
    <TooltipPortal
      visible={tooltipVisible}
      x={tooltipPos.x}
      y={tooltipPos.y}
      color={color}
      entity={entity}
      refs={refs}
      onNavigate={handleNavigateToRef}
      onNavigateToEntity={handleNavigateToEntity}
      onMouseEnter={showTooltip}
      onMouseLeave={scheduleHide}
    />
  );

  if (variant === 'chip') {
    return (
      <>
        <button
          ref={btnRef}
          type="button"
          onClick={() => navigateToSlug(slug)}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={scheduleHide}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-all duration-200 cursor-pointer"
          style={{
            color,
            border: `1px solid ${color}40`,
            background: `${color}10`,
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.background = `${color}20`;
            e.currentTarget.style.borderColor = `${color}70`;
            e.currentTarget.style.transform = 'translateY(-1px)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = `${color}10`;
            e.currentTarget.style.borderColor = `${color}40`;
            e.currentTarget.style.transform = 'none';
          }}
        >
          {label}
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
        {tooltipPortal}
      </>
    );
  }

  if (variant === 'inline') {
    return (
      <>
        <button
          ref={btnRef}
          type="button"
          onClick={() => navigateToSlug(slug)}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={scheduleHide}
          className="inline underline underline-offset-2 decoration-dotted transition-opacity duration-150 cursor-pointer"
          style={{ color, textDecorationColor: `${color}60` }}
          onMouseOver={(e) => (e.currentTarget.style.opacity = '0.8')}
          onMouseOut={(e) => (e.currentTarget.style.opacity = '1')}
        >
          {label}
        </button>
        {tooltipPortal}
      </>
    );
  }

  // card variant
  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={() => navigateToSlug(slug)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={scheduleHide}
        className="flex flex-col rounded-xl p-3 text-left transition-all duration-200 w-full"
        style={{
          background: `${color}08`,
          border: `1px solid ${color}20`,
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.background = `${color}14`;
          e.currentTarget.style.borderColor = `${color}35`;
          e.currentTarget.style.transform = 'translateY(-2px)';
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.background = `${color}08`;
          e.currentTarget.style.borderColor = `${color}20`;
          e.currentTarget.style.transform = 'none';
        }}
      >
        <span className="mb-1 text-[9px] font-bold tracking-[0.2em] uppercase" style={{ color }}>
          {entity.type.replace('-', ' ')}
        </span>
        <span className="text-sm font-semibold" style={{ color: 'rgba(255,255,255,0.85)' }}>
          {entity.title}
        </span>
        {entity.summary && (
          <span className="mt-1 text-xs line-clamp-2" style={{ color: 'rgba(255,255,255,0.40)' }}>
            {entity.summary}
          </span>
        )}
      </button>
      {tooltipPortal}
    </>
  );
}
