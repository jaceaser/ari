'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { usePresentation } from '@/contexts/PresentationContext';
import { CodexLink } from './CodexLink';
import type {
  CodexEntity,
  Topic,
  CaseStudy,
  Pathway,
  GlossaryTerm,
  OperatorCard,
} from '@/types/codex';

const TYPE_COLORS: Record<string, string> = {
  topic: 'hsl(41 92% 67%)',
  'case-study': 'hsl(173 58% 45%)',
  pathway: 'hsl(270 60% 65%)',
  'operator-card': 'hsl(25 90% 60%)',
  glossary: 'hsl(210 60% 60%)',
};

// ─── Sub-accordion ────────────────────────────────────────────────────────────

function SubAccordion({
  title,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-white/[0.05]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-xs font-semibold uppercase tracking-[0.15em]" style={{ color: 'rgba(255,255,255,0.5)' }}>
          {title}{' '}
          {count !== undefined && (
            <span style={{ color: 'rgba(255,255,255,0.25)' }}>({count})</span>
          )}
        </span>
        <motion.svg
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </motion.svg>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Section accordion (chapter level) ───────────────────────────────────────

function SectionAccordion({
  title,
  count,
  visitedCount,
  color,
  children,
}: {
  title: string;
  count: number;
  visitedCount: number;
  color: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const pct = count > 0 ? (visitedCount / count) * 100 : 0;

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-6 py-4 text-left"
      >
        <div className="flex items-center gap-4">
          <motion.svg
            animate={{ rotate: open ? 90 : 0 }}
            transition={{ duration: 0.2 }}
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.5}
            style={{ color, flexShrink: 0 }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </motion.svg>
          <span
            className="text-sm font-bold uppercase tracking-[0.15em]"
            style={{ color }}
          >
            {title}
          </span>
          <span className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>
            {count}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>
            {visitedCount}/{count}
          </div>
          <div
            className="h-1 w-16 overflow-hidden rounded-full"
            style={{ background: 'rgba(255,255,255,0.10)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%`, background: color }}
            />
          </div>
        </div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-2">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Entity-type content components ──────────────────────────────────────────

function TopicEntityContent({ entity }: { entity: Topic }) {
  return (
    <div>
      {entity.plainEnglish && (
        <div
          className="mx-4 mb-2 mt-4 rounded-lg p-3"
          style={{
            background: 'rgba(247,195,93,0.06)',
            borderLeft: '3px solid hsl(41 92% 67%)',
          }}
        >
          <p className="text-sm italic" style={{ color: 'rgba(255,255,255,0.75)' }}>
            &ldquo;{entity.plainEnglish}&rdquo;
          </p>
        </div>
      )}
      {entity.whyItMatters && (
        <SubAccordion title="Why It Matters">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.whyItMatters}
          </p>
        </SubAccordion>
      )}
      {entity.whenUsed && (
        <SubAccordion title="When To Use It">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.whenUsed}
          </p>
        </SubAccordion>
      )}
      {entity.risks?.length > 0 && (
        <SubAccordion title="Risks" count={entity.risks.length}>
          <ul className="space-y-2">
            {entity.risks.map((r, i) => (
              <li key={i} className="flex gap-2 text-sm" style={{ color: 'rgba(251,191,36,0.7)' }}>
                <span>⚠</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </SubAccordion>
      )}
      {entity.relatedNodes?.length > 0 && (
        <SubAccordion title="Related Concepts" count={entity.relatedNodes.length}>
          <div className="flex flex-wrap gap-2">
            {entity.relatedNodes.map((slug) => (
              <CodexLink key={slug} slug={slug} variant="chip" />
            ))}
          </div>
        </SubAccordion>
      )}
      {entity.operatorNotes && (
        <SubAccordion title="Operator Notes">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.operatorNotes}
          </p>
        </SubAccordion>
      )}
      {entity.body && (
        <SubAccordion title="Full Content">
          <div
            className="prose prose-invert prose-sm max-w-none [&_h1]:text-white/90 [&_h2]:text-white/80 [&_h3]:text-white/70 [&_strong]:text-white/80"
            style={{ color: 'rgba(255,255,255,0.6)' }}
            dangerouslySetInnerHTML={{ __html: entity.body }}
          />
        </SubAccordion>
      )}
    </div>
  );
}

function CaseStudyEntityContent({ entity }: { entity: CaseStudy }) {
  return (
    <div>
      {entity.scenario && (
        <SubAccordion title="Scenario" defaultOpen>
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.scenario}
          </p>
        </SubAccordion>
      )}
      {entity.play && (
        <SubAccordion title="The Play">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.play}
          </p>
        </SubAccordion>
      )}
      {entity.outcome && (
        <SubAccordion title="Outcome">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.outcome}
          </p>
        </SubAccordion>
      )}
      {entity.takeaway && (
        <SubAccordion title="Takeaway">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.takeaway}
          </p>
        </SubAccordion>
      )}
      {entity.doctrines?.length > 0 && (
        <SubAccordion title="Doctrines Used" count={entity.doctrines.length}>
          <div className="flex flex-wrap gap-2">
            {entity.doctrines.map((slug) => (
              <CodexLink key={slug} slug={slug} variant="chip" />
            ))}
          </div>
        </SubAccordion>
      )}
    </div>
  );
}

function PathwayEntityContent({ entity }: { entity: Pathway }) {
  return (
    <div>
      {entity.entryCondition && (
        <div
          className="mx-4 mb-2 mt-4 rounded-lg p-3"
          style={{
            background: 'rgba(139,92,246,0.08)',
            borderLeft: '3px solid hsl(270 60% 65%)',
          }}
        >
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'hsl(270 60% 65%)' }}>
            Entry Condition
          </p>
          <p className="mt-1 text-sm" style={{ color: 'rgba(255,255,255,0.7)' }}>
            {entity.entryCondition}
          </p>
        </div>
      )}
      {entity.steps?.length > 0 && (
        <SubAccordion title="Steps" count={entity.steps.length} defaultOpen>
          <div className="space-y-3">
            {entity.steps.map((step) => (
              <div key={step.order} className="flex gap-3">
                <div
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                  style={{ background: 'rgba(139,92,246,0.15)', color: 'hsl(270 60% 65%)' }}
                >
                  {step.order}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold" style={{ color: 'rgba(255,255,255,0.8)' }}>
                      {step.label}
                    </span>
                    {step.topicSlug && <CodexLink slug={step.topicSlug} variant="chip" />}
                  </div>
                  {step.decisionPoints && step.decisionPoints.length > 0 && (
                    <ul className="mt-1 space-y-1">
                      {step.decisionPoints.map((dp, i) => (
                        <li key={i} className="text-xs" style={{ color: 'rgba(255,255,255,0.45)' }}>
                          → {dp}
                        </li>
                      ))}
                    </ul>
                  )}
                  {step.risks && step.risks.length > 0 && (
                    <ul className="mt-1 space-y-1">
                      {step.risks.map((r, i) => (
                        <li key={i} className="text-xs" style={{ color: 'rgba(251,191,36,0.6)' }}>
                          ⚠ {r}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ))}
          </div>
        </SubAccordion>
      )}
      {entity.stateSensitivity && (
        <SubAccordion title="State Sensitivity">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.stateSensitivity}
          </p>
        </SubAccordion>
      )}
    </div>
  );
}

function GlossaryEntityContent({ entity }: { entity: GlossaryTerm }) {
  return (
    <div>
      {entity.definition && (
        <div className="px-4 pt-4 pb-2">
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.7)' }}>
            {entity.definition}
          </p>
        </div>
      )}
      {entity.plainEnglish && (
        <SubAccordion title="Plain English">
          <p className="text-sm leading-relaxed italic" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {entity.plainEnglish}
          </p>
        </SubAccordion>
      )}
      {entity.relatedTerms?.length > 0 && (
        <SubAccordion title="Related Terms" count={entity.relatedTerms.length}>
          <div className="flex flex-wrap gap-2">
            {entity.relatedTerms.map((slug) => (
              <CodexLink key={slug} slug={slug} variant="chip" />
            ))}
          </div>
        </SubAccordion>
      )}
    </div>
  );
}

function OperatorCardEntityContent({ entity }: { entity: OperatorCard }) {
  const storageKey = `codex-opchecklist-${entity.slug}`;
  const [checked, setChecked] = useState<Set<number>>(() => {
    if (typeof window === 'undefined') return new Set();
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });

  const toggle = (i: number) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      try {
        localStorage.setItem(storageKey, JSON.stringify(Array.from(next)));
      } catch { /* ignore */ }
      return next;
    });
  };

  return (
    <div>
      {entity.checklist?.length > 0 && (
        <SubAccordion title="Checklist" count={entity.checklist.length} defaultOpen>
          <ul className="space-y-2">
            {entity.checklist.map((item, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <button
                  type="button"
                  onClick={() => toggle(i)}
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded"
                  style={{
                    border: `1px solid ${checked.has(i) ? 'hsl(25 90% 60%)' : 'rgba(255,255,255,0.25)'}`,
                    background: checked.has(i) ? 'hsl(25 90% 60% / 0.2)' : 'transparent',
                  }}
                >
                  {checked.has(i) && (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="hsl(25 90% 60%)" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
                <span
                  className="text-sm leading-relaxed"
                  style={{
                    color: checked.has(i) ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.7)',
                    textDecoration: checked.has(i) ? 'line-through' : 'none',
                  }}
                >
                  {item}
                </span>
              </li>
            ))}
          </ul>
        </SubAccordion>
      )}
      {entity.commonMistakes?.length > 0 && (
        <SubAccordion title="Common Mistakes" count={entity.commonMistakes.length}>
          <ul className="space-y-2">
            {entity.commonMistakes.map((m, i) => (
              <li key={i} className="flex gap-2 text-sm" style={{ color: 'rgba(248,113,113,0.75)' }}>
                <span>✗</span>
                <span>{m}</span>
              </li>
            ))}
          </ul>
        </SubAccordion>
      )}
    </div>
  );
}

// ─── Entity card ──────────────────────────────────────────────────────────────

function EntityCard({
  entity,
  slideIndex,
  visitedSlides,
}: {
  entity: CodexEntity;
  slideIndex: number;
  visitedSlides: Set<string>;
}) {
  const [open, setOpen] = useState(false);
  const { navigateToIndex, navigateToSlug, setExplorerOpen, crossRefIndex } = usePresentation();

  const visited =
    visitedSlides.has(`topic-${entity.slug}`) ||
    visitedSlides.has(`cs-${entity.slug}`) ||
    visitedSlides.has(`pathway-${entity.slug}`);

  const color = TYPE_COLORS[entity.type] ?? TYPE_COLORS.topic;
  const refCount = crossRefIndex[entity.slug]?.length ?? 0;

  return (
    <div
      className="mb-1 overflow-hidden rounded-xl"
      style={{
        border: `1px solid ${open ? color + '20' : 'rgba(255,255,255,0.05)'}`,
        transition: 'border-color 0.2s',
      }}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <motion.svg
            animate={{ rotate: open ? 90 : 0 }}
            transition={{ duration: 0.2 }}
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.5}
            style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </motion.svg>
          <span className="truncate text-sm font-bold" style={{ color: 'rgba(255,255,255,0.85)' }}>
            {entity.title}
          </span>
          {refCount > 0 && (
            <span
              className="shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold"
              style={{ background: `${color}15`, color }}
            >
              {refCount} refs
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 ml-2">
          <span
            className="text-[9px] font-bold uppercase tracking-wider"
            style={{ color }}
          >
            {entity.type.replace('-', ' ')}
          </span>
          <span
            title={visited ? 'Visited' : 'Not visited'}
            style={{
              color: visited ? 'hsl(41 92% 67%)' : 'rgba(255,255,255,0.2)',
              fontSize: 10,
            }}
          >
            {visited ? '✓' : '○'}
          </span>
        </div>
      </button>

      {/* Body */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/[0.05]">
              {entity.type === 'topic' && (
                <TopicEntityContent entity={entity as Topic} />
              )}
              {entity.type === 'case-study' && (
                <CaseStudyEntityContent entity={entity as CaseStudy} />
              )}
              {entity.type === 'pathway' && (
                <PathwayEntityContent entity={entity as Pathway} />
              )}
              {entity.type === 'glossary' && (
                <GlossaryEntityContent entity={entity as GlossaryTerm} />
              )}
              {entity.type === 'operator-card' && (
                <OperatorCardEntityContent entity={entity as OperatorCard} />
              )}

              {/* Cross-references */}
              {refCount > 0 && (
                <SubAccordion title="Referenced In" count={refCount}>
                  <div className="flex flex-wrap gap-2">
                    {crossRefIndex[entity.slug].map((ref, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => {
                          navigateToSlug(ref.sourceSlug);
                          setExplorerOpen(false);
                        }}
                        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-left transition-all"
                        style={{
                          background: `${TYPE_COLORS[ref.sourceType] ?? TYPE_COLORS.topic}10`,
                          border: `1px solid ${TYPE_COLORS[ref.sourceType] ?? TYPE_COLORS.topic}25`,
                          color: TYPE_COLORS[ref.sourceType] ?? TYPE_COLORS.topic,
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = `${TYPE_COLORS[ref.sourceType] ?? TYPE_COLORS.topic}20`;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = `${TYPE_COLORS[ref.sourceType] ?? TYPE_COLORS.topic}10`;
                        }}
                      >
                        <span className="font-semibold">{ref.sourceTitle}</span>
                        <span style={{ color: 'rgba(255,255,255,0.3)' }}>·</span>
                        <span style={{ color: 'rgba(255,255,255,0.4)' }}>{ref.context}</span>
                      </button>
                    ))}
                  </div>
                </SubAccordion>
              )}

              {/* Jump to slide */}
              {slideIndex !== -1 && (
                <div className="flex justify-end px-4 pb-3 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      navigateToIndex(slideIndex);
                      setExplorerOpen(false);
                    }}
                    className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all"
                    style={{
                      background: `${color}12`,
                      border: `1px solid ${color}30`,
                      color,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = `${color}20`;
                      e.currentTarget.style.borderColor = `${color}50`;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = `${color}12`;
                      e.currentTarget.style.borderColor = `${color}30`;
                    }}
                  >
                    → Jump to Slide
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Main ContentExplorer ─────────────────────────────────────────────────────

interface ContentExplorerProps {
  open: boolean;
  onClose: () => void;
  visitedSlides: Set<string>;
}

export function ContentExplorer({ open, onClose, visitedSlides }: ContentExplorerProps) {
  const { course, slides } = usePresentation();

  const slideIndexFor = (slug: string): number =>
    slides.findIndex(
      (s) =>
        s.data?.topic?.slug === slug ||
        s.data?.caseStudy?.slug === slug ||
        s.data?.pathway?.slug === slug
    );

  const isVisited = (entity: CodexEntity): boolean => {
    return (
      visitedSlides.has(`topic-${entity.slug}`) ||
      visitedSlides.has(`cs-${entity.slug}`) ||
      visitedSlides.has(`pathway-${entity.slug}`)
    );
  };

  const topicsSorted = [...course.topics].sort(
    (a, b) => (a.order ?? 99) - (b.order ?? 99)
  );
  const glossarySorted = [...course.glossary].sort((a, b) =>
    a.title.localeCompare(b.title)
  );

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[65]"
            style={{ background: 'rgba(0,0,0,0.5)' }}
            onClick={onClose}
          />

          {/* Panel — slides up from bottom */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="fixed inset-x-0 bottom-0 z-[70] flex flex-col"
            style={{
              top: 0,
              background: 'rgba(4,4,4,0.99)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
            }}
          >
            {/* Header */}
            <div
              className="flex shrink-0 items-center justify-between px-6 py-4"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div>
                <div className="mb-0.5 flex items-center gap-2">
                  <span
                    className="text-xs font-bold uppercase tracking-[0.25em]"
                    style={{ color: 'hsl(41 92% 67%)' }}
                  >
                    ARI · CODEX
                  </span>
                  <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>·</span>
                  <span
                    className="text-xs uppercase tracking-wider"
                    style={{ color: 'rgba(255,255,255,0.3)' }}
                  >
                    Content Explorer
                  </span>
                </div>
                <h2 className="text-base font-bold" style={{ color: 'rgba(255,255,255,0.8)' }}>
                  {course.config.title}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-2 transition-colors"
                style={{ color: 'rgba(255,255,255,0.4)' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
                aria-label="Close explorer"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-2 py-4">
              {/* Part I — Topics */}
              <SectionAccordion
                title="Part I — The Strategy"
                count={topicsSorted.length}
                visitedCount={topicsSorted.filter(isVisited).length}
                color="hsl(41 92% 67%)"
              >
                {topicsSorted.map((entity) => (
                  <EntityCard
                    key={entity.slug}
                    entity={entity}
                    slideIndex={slideIndexFor(entity.slug)}
                    visitedSlides={visitedSlides}
                  />
                ))}
              </SectionAccordion>

              {/* Part II — Case Studies */}
              {course.caseStudies.length > 0 && (
                <SectionAccordion
                  title="Part II — Case Studies"
                  count={course.caseStudies.length}
                  visitedCount={course.caseStudies.filter(isVisited).length}
                  color="hsl(173 58% 45%)"
                >
                  {course.caseStudies.map((entity) => (
                    <EntityCard
                      key={entity.slug}
                      entity={entity}
                      slideIndex={slideIndexFor(entity.slug)}
                      visitedSlides={visitedSlides}
                    />
                  ))}
                </SectionAccordion>
              )}

              {/* Part III — Pathways */}
              {course.pathways.length > 0 && (
                <SectionAccordion
                  title="Part III — Pathways"
                  count={course.pathways.length}
                  visitedCount={course.pathways.filter(isVisited).length}
                  color="hsl(270 60% 65%)"
                >
                  {course.pathways.map((entity) => (
                    <EntityCard
                      key={entity.slug}
                      entity={entity}
                      slideIndex={slideIndexFor(entity.slug)}
                      visitedSlides={visitedSlides}
                    />
                  ))}
                </SectionAccordion>
              )}

              {/* Operator Cards */}
              {course.operatorCards.length > 0 && (
                <SectionAccordion
                  title="Operator Reference"
                  count={course.operatorCards.length}
                  visitedCount={0}
                  color="hsl(25 90% 60%)"
                >
                  {course.operatorCards.map((entity) => (
                    <EntityCard
                      key={entity.slug}
                      entity={entity}
                      slideIndex={-1}
                      visitedSlides={visitedSlides}
                    />
                  ))}
                </SectionAccordion>
              )}

              {/* Glossary */}
              {course.glossary.length > 0 && (
                <SectionAccordion
                  title="Glossary"
                  count={course.glossary.length}
                  visitedCount={0}
                  color="hsl(210 60% 60%)"
                >
                  {glossarySorted.map((entity) => (
                    <EntityCard
                      key={entity.slug}
                      entity={entity}
                      slideIndex={-1}
                      visitedSlides={visitedSlides}
                    />
                  ))}
                </SectionAccordion>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
