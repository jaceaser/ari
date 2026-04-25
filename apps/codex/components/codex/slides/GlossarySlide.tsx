'use client';

import { motion } from 'framer-motion';
import type { GlossaryTerm } from '@/types/codex';
import { CodexLink } from '../CodexLink';
import { useTranslations } from '@/lib/locale-context';

const noiseUrl =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E";

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } },
};

const itemVariants = {
  hidden: { y: 16, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

interface GlossarySlideProps {
  terms: GlossaryTerm[];
}

export function GlossarySlide({ terms }: GlossarySlideProps) {
  const t = useTranslations();
  const sorted = [...terms].sort((a, b) => a.title.localeCompare(b.title));

  // Group by first letter
  const groups: Record<string, GlossaryTerm[]> = {};
  for (const term of sorted) {
    const letter = term.title[0].toUpperCase();
    if (!groups[letter]) groups[letter] = [];
    groups[letter].push(term);
  }
  const letters = Object.keys(groups).sort();

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-[#06080f]">
      {/* Noise */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />
      {/* Blue glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 60% 50% at 10% 90%, rgba(59,100,220,0.08), transparent)',
        }}
      />

      <motion.div
        className="relative z-10 flex h-full flex-col overflow-y-auto px-8 py-10 lg:px-16"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Label */}
        <motion.div variants={itemVariants} className="mb-2">
          <span
            className="text-xs font-bold tracking-[0.3em] uppercase"
            style={{ color: 'hsl(220 70% 65%)' }}
          >
            {t.referenceLabel}
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          variants={itemVariants}
          className="mb-8 text-[40px] font-black leading-tight tracking-tight text-white sm:text-[48px] lg:text-[52px]"
        >
          {t.glossaryTitle}
        </motion.h1>

        {/* Terms grid */}
        <div className="space-y-8">
          {letters.map((letter) => (
            <motion.div key={letter} variants={itemVariants}>
              {/* Letter header */}
              <div
                className="mb-3 flex items-center gap-3"
              >
                <span
                  className="text-2xl font-black"
                  style={{ color: 'hsl(220 70% 65%)' }}
                >
                  {letter}
                </span>
                <div className="flex-1 h-px" style={{ background: 'rgba(59,100,220,0.15)' }} />
              </div>

              {/* Terms in this letter group */}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {groups[letter].map((term) => (
                  <div
                    key={term.slug}
                    className="rounded-xl p-4"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.07)',
                    }}
                  >
                    <div className="mb-1 flex items-start justify-between gap-2">
                      <h3 className="text-sm font-bold text-white/90">{term.title}</h3>
                      {term.aliases && term.aliases.length > 0 && (
                        <span className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold tracking-wide"
                          style={{ background: 'rgba(59,100,220,0.15)', color: 'hsl(220 70% 65%)' }}>
                          {term.aliases[0]}
                        </span>
                      )}
                    </div>

                    {term.plainEnglish ? (
                      <p className="mb-2 text-xs italic text-white/40 leading-relaxed">
                        &ldquo;{term.plainEnglish}&rdquo;
                      </p>
                    ) : null}

                    <p className="text-xs text-white/55 leading-relaxed">
                      {term.definition || term.summary}
                    </p>

                    {term.relatedTerms && term.relatedTerms.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {term.relatedTerms.map((slug) => (
                          <CodexLink key={slug} slug={slug} variant="chip" />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
