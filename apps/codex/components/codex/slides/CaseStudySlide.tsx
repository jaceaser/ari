'use client';

import { motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import type { CaseStudy, CodexEntity } from '@/types/codex';
import { CodexLink } from '../CodexLink';

const noiseUrl =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E";

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1, delayChildren: 0.15 } },
};

const itemVariants = {
  hidden: { y: 24, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

function extractNumbers(text: string): { original: string; value: number }[] {
  const results: { original: string; value: number }[] = [];
  const dollarRe = /\$[\d,.]+[KkMmBb]?/g;
  let m: RegExpExecArray | null;
  while ((m = dollarRe.exec(text)) !== null) {
    const raw = m[0];
    let val = parseFloat(raw.replace(/[$,]/g, ''));
    if (raw.match(/[Kk]$/)) val *= 1000;
    if (raw.match(/[Mm]$/)) val *= 1_000_000;
    if (raw.match(/[Bb]$/)) val *= 1_000_000_000;
    results.push({ original: raw, value: val });
  }
  return results.slice(0, 1);
}

function AnimatedNumber({ target, prefix = '' }: { target: number; prefix?: string }) {
  const [displayed, setDisplayed] = useState(0);
  const startTime = useRef<number | null>(null);
  const duration = 1500;

  useEffect(() => {
    startTime.current = null;
    let raf: number;

    const animate = (ts: number) => {
      if (startTime.current === null) startTime.current = ts;
      const elapsed = ts - startTime.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(target * eased));
      if (progress < 1) raf = requestAnimationFrame(animate);
    };

    raf = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  const formatted =
    displayed >= 1_000_000
      ? `$${(displayed / 1_000_000).toFixed(1)}M`
      : displayed >= 1_000
      ? `$${(displayed / 1_000).toFixed(0)}K`
      : `${prefix}${displayed.toLocaleString()}`;

  return <span>{formatted}</span>;
}

interface CaseStudySlideProps {
  caseStudy: CaseStudy;
  courseSlug: string;
  allEntities: Record<string, CodexEntity>;
}

export function CaseStudySlide({ caseStudy }: CaseStudySlideProps) {
  const numbers = extractNumbers(caseStudy.outcome ?? '');
  const bigNumber = numbers[0];

  const hasDoctrineSlugs = caseStudy.doctrines && caseStudy.doctrines.length > 0;
  const hasRelatedNodes = caseStudy.relatedNodes && caseStudy.relatedNodes.length > 0;

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-[#080d0c]">
      {/* Noise */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />

      {/* Teal glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 60% 40% at 80% 20%, rgba(59,178,152,0.06), transparent)',
        }}
      />

      <motion.div
        className="relative z-10 flex h-full flex-col justify-center overflow-y-auto px-8 py-10 lg:px-16"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Label */}
        <motion.div variants={itemVariants} className="mb-4">
          <span
            className="text-xs font-bold tracking-[0.3em] uppercase"
            style={{ color: 'hsl(173 58% 45%)' }}
          >
            Case Study
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          variants={itemVariants}
          className="mb-8 max-w-3xl text-[40px] font-black leading-tight tracking-tight text-white sm:text-[48px] lg:text-[56px]"
        >
          {caseStudy.title.toUpperCase()}
        </motion.h1>

        {/* Three act panels */}
        <motion.div
          variants={itemVariants}
          className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          {/* Scenario */}
          <div
            className="flex flex-col rounded-2xl p-5"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <p
              className="mb-3 text-[10px] font-bold tracking-[0.25em] uppercase"
              style={{ color: 'hsl(173 58% 45%)' }}
            >
              The Scenario
            </p>
            <p className="flex-1 text-sm text-white/60 leading-relaxed line-clamp-6">
              {caseStudy.scenario ?? caseStudy.summary}
            </p>
          </div>

          {/* The Play */}
          <div
            className="flex flex-col rounded-2xl p-5"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <p
              className="mb-3 text-[10px] font-bold tracking-[0.25em] uppercase"
              style={{ color: 'hsl(173 58% 45%)' }}
            >
              The Play
            </p>
            <p className="flex-1 text-sm text-white/60 leading-relaxed line-clamp-6">
              {caseStudy.play ?? '—'}
            </p>
          </div>

          {/* Outcome */}
          <div
            className="flex flex-col rounded-2xl p-5"
            style={{
              background: 'rgba(59,178,152,0.06)',
              border: '1px solid rgba(59,178,152,0.15)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <p
              className="mb-3 text-[10px] font-bold tracking-[0.25em] uppercase"
              style={{ color: 'hsl(173 58% 45%)' }}
            >
              Outcome
            </p>
            {bigNumber ? (
              <div className="mb-2">
                <div
                  className="text-[36px] font-black leading-none"
                  style={{ color: 'hsl(41 92% 67%)' }}
                >
                  <AnimatedNumber target={bigNumber.value} />
                </div>
                <p className="mt-1 text-xs text-white/40">return</p>
              </div>
            ) : null}
            <p className="text-sm text-white/60 leading-relaxed line-clamp-4">
              {caseStudy.outcome ?? '—'}
            </p>
          </div>
        </motion.div>

        {/* Takeaway */}
        {caseStudy.takeaway && (
          <motion.div
            variants={itemVariants}
            className="mb-5 rounded-2xl p-5"
            style={{
              background: 'rgba(247,195,93,0.06)',
              border: '1px solid rgba(247,195,93,0.2)',
            }}
          >
            <p className="mb-1 text-[10px] font-bold tracking-[0.25em] uppercase text-amber-400/60">
              Takeaway
            </p>
            <p className="text-sm font-medium text-white/80 leading-relaxed">
              {caseStudy.takeaway}
            </p>
          </motion.div>
        )}

        {/* Doctrines / Related links */}
        {(hasDoctrineSlugs || hasRelatedNodes) && (
          <motion.div variants={itemVariants} className="flex flex-wrap gap-3">
            {hasDoctrineSlugs && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-white/20">
                  Doctrines:
                </span>
                {caseStudy.doctrines.map((slug) => (
                  <CodexLink key={slug} slug={slug} variant="chip" />
                ))}
              </div>
            )}
            {hasRelatedNodes && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-white/20">
                  Related:
                </span>
                {caseStudy.relatedNodes.map((slug) => (
                  <CodexLink key={slug} slug={slug} variant="chip" />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
