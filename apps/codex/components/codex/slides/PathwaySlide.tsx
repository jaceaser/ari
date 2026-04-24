'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';
import type { Pathway, CodexEntity } from '@/types/codex';
import { CodexLink } from '../CodexLink';
import { usePresentation } from '@/contexts/PresentationContext';

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

const stepVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: {
      delay: 0.3 + i * 0.15,
      duration: 0.4,
      ease: [0.25, 0.46, 0.45, 0.94] as const,
    },
  }),
};

interface PathwaySlideProps {
  pathway: Pathway;
  courseSlug: string;
  allEntities: Record<string, CodexEntity>;
}

export function PathwaySlide({ pathway }: PathwaySlideProps) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const { course } = usePresentation();
  const steps = [...pathway.steps].sort((a, b) => a.order - b.order);

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-[#0a0810]">
      {/* Noise */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />

      {/* Purple glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 50% 50% at 20% 80%, rgba(147,112,200,0.08), transparent)',
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
            style={{ color: 'hsl(270 60% 65%)' }}
          >
            Pathway
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          variants={itemVariants}
          className="mb-2 text-[40px] font-black leading-tight tracking-tight text-white sm:text-[48px] lg:text-[52px]"
        >
          {pathway.title.toUpperCase()}
        </motion.h1>

        {/* Entry condition */}
        {pathway.entryCondition && (
          <motion.p variants={itemVariants} className="mb-8 text-base italic text-white/40">
            Entry: {pathway.entryCondition}
          </motion.p>
        )}

        {/* Steps — horizontal on desktop, vertical on mobile */}
        <div className="hidden md:block">
          {/* Horizontal connector line */}
          <div className="mb-2 flex items-center">
            {steps.map((step, i) => {
              const topicEntity = course.allEntities[step.topicSlug];
              return (
                <div key={step.order} className="flex items-center flex-1">
                  <motion.div
                    custom={i}
                    variants={stepVariants}
                    initial="hidden"
                    animate="visible"
                    onClick={() => setExpandedStep(expandedStep === i ? null : i)}
                    className="group relative flex flex-col items-center cursor-pointer"
                    style={{ minWidth: 0, flex: 1 }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setExpandedStep(expandedStep === i ? null : i)}
                  >
                    {/* Step circle */}
                    <div
                      className="relative z-10 mb-2 flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold transition-all duration-200"
                      style={{
                        background:
                          expandedStep === i
                            ? 'hsl(270 60% 65%)'
                            : 'rgba(147,112,200,0.15)',
                        border: `2px solid ${
                          expandedStep === i
                            ? 'hsl(270 60% 65%)'
                            : 'rgba(147,112,200,0.4)'
                        }`,
                        color: expandedStep === i ? '#0a0810' : 'hsl(270 60% 65%)',
                        boxShadow: expandedStep === i ? '0 0 20px rgba(147,112,200,0.4)' : 'none',
                      }}
                    >
                      {i + 1}
                    </div>
                    {/* Step label */}
                    <p
                      className="max-w-[100px] text-center text-xs font-medium leading-tight transition-colors"
                      style={{
                        color: expandedStep === i ? 'hsl(270 60% 65%)' : 'rgba(255,255,255,0.5)',
                      }}
                    >
                      {step.label}
                    </p>
                    {/* Topic link if entity exists */}
                    {topicEntity && (
                      <div
                        className="mt-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <CodexLink slug={step.topicSlug} variant="inline">
                          <span className="text-[9px]">{topicEntity.title}</span>
                        </CodexLink>
                      </div>
                    )}
                  </motion.div>

                  {/* Connector */}
                  {i < steps.length - 1 && (
                    <div
                      className="h-px flex-1 mx-1"
                      style={{
                        background:
                          'linear-gradient(90deg, rgba(147,112,200,0.4), rgba(147,112,200,0.2))',
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* Expanded step detail */}
          <AnimatePresence>
            {expandedStep !== null && steps[expandedStep] && (
              <motion.div
                key={expandedStep}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
                className="mt-4 overflow-hidden"
              >
                <div
                  className="rounded-2xl p-5"
                  style={{
                    background: 'rgba(147,112,200,0.06)',
                    border: '1px solid rgba(147,112,200,0.15)',
                  }}
                >
                  <h3 className="mb-3 font-bold text-white/90">
                    Step {expandedStep + 1}: {steps[expandedStep].label}
                  </h3>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {steps[expandedStep].decisionPoints &&
                      steps[expandedStep].decisionPoints!.length > 0 && (
                        <div>
                          <p className="mb-2 text-[10px] font-bold tracking-[0.2em] uppercase text-white/30">
                            Decision Points
                          </p>
                          <ul className="space-y-1.5">
                            {steps[expandedStep].decisionPoints!.map((dp, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-white/60">
                                <span style={{ color: 'hsl(270 60% 65%)' }}>→</span>
                                {dp}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    {steps[expandedStep].risks && steps[expandedStep].risks!.length > 0 && (
                      <div>
                        <p className="mb-2 text-[10px] font-bold tracking-[0.2em] uppercase text-white/30">
                          Risks
                        </p>
                        <ul className="space-y-1.5">
                          {steps[expandedStep].risks!.map((risk, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-amber-300/70">
                              <span>⚠</span>
                              {risk}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Mobile: vertical steps */}
        <div className="block md:hidden space-y-4">
          {steps.map((step, i) => {
            const topicEntity = course.allEntities[step.topicSlug];
            return (
              <motion.div
                key={step.order}
                custom={i}
                variants={stepVariants}
                initial="hidden"
                animate="visible"
                onClick={() => setExpandedStep(expandedStep === i ? null : i)}
                className="w-full text-left cursor-pointer"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && setExpandedStep(expandedStep === i ? null : i)}
              >
                <div
                  className="flex items-start gap-4 rounded-xl p-4"
                  style={{
                    background:
                      expandedStep === i ? 'rgba(147,112,200,0.1)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${
                      expandedStep === i ? 'rgba(147,112,200,0.3)' : 'rgba(255,255,255,0.07)'
                    }`,
                  }}
                >
                  <div
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold"
                    style={{
                      background:
                        expandedStep === i
                          ? 'hsl(270 60% 65%)'
                          : 'rgba(147,112,200,0.15)',
                      color: expandedStep === i ? '#0a0810' : 'hsl(270 60% 65%)',
                    }}
                  >
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-white/80">{step.label}</p>
                    {topicEntity && (
                      <div
                        className="mt-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <CodexLink slug={step.topicSlug} variant="inline">
                          <span className="text-[10px]">{topicEntity.title}</span>
                        </CodexLink>
                      </div>
                    )}
                    <AnimatePresence>
                      {expandedStep === i && (step.decisionPoints?.length || step.risks?.length) ? (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="mt-3 space-y-2 overflow-hidden"
                        >
                          {step.decisionPoints?.map((dp, j) => (
                            <p key={j} className="text-xs text-white/50">→ {dp}</p>
                          ))}
                          {step.risks?.map((r, j) => (
                            <p key={j} className="text-xs text-amber-400/60">⚠ {r}</p>
                          ))}
                        </motion.div>
                      ) : null}
                    </AnimatePresence>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* State sensitivity note */}
        {pathway.stateSensitivity && (
          <motion.div
            variants={itemVariants}
            className="mt-6 flex items-start gap-3 rounded-xl p-4"
            style={{
              background: 'rgba(251,191,36,0.06)',
              border: '1px solid rgba(251,191,36,0.15)',
            }}
          >
            <span className="text-amber-400">⚠</span>
            <div>
              <p className="text-[10px] font-bold tracking-[0.2em] uppercase text-amber-400/60 mb-1">
                State Sensitivity
              </p>
              <p className="text-sm text-white/50">{pathway.stateSensitivity}</p>
            </div>
          </motion.div>
        )}

        {/* Related nodes */}
        {pathway.relatedNodes && pathway.relatedNodes.length > 0 && (
          <motion.div variants={itemVariants} className="mt-5 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-white/20">
              Related:
            </span>
            {pathway.relatedNodes.map((slug) => (
              <CodexLink key={slug} slug={slug} variant="chip" />
            ))}
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
