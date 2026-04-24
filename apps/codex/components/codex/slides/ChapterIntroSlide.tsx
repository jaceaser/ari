'use client';

import { motion } from 'framer-motion';

const noiseUrl =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E";

const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};

const item = {
  hidden: { y: 24, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.55, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

interface ChapterIntroSlideProps {
  partNumber: string;
  title: string;
  description: string;
  slideCount: number;
  items?: string[];
}

export function ChapterIntroSlide({
  partNumber,
  title,
  description,
  slideCount,
  items,
}: ChapterIntroSlideProps) {
  const displayItems = items?.slice(0, 8) ?? [];
  const overflow = (items?.length ?? 0) - displayItems.length;

  return (
    <div className="relative flex h-full w-full overflow-hidden bg-[#050505]">
      {/* Noise texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />

      {/* Subtle radial glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            'radial-gradient(ellipse 60% 50% at 30% 50%, rgba(247,195,93,0.05), transparent)',
        }}
      />

      {/* Left accent bar */}
      <div
        className="absolute left-0 top-0 h-full w-1"
        style={{
          background: 'linear-gradient(180deg, transparent, hsl(41 92% 67% / 0.55), transparent)',
        }}
      />

      <motion.div
        className="relative z-10 flex h-full w-full flex-col justify-center px-10 py-10 lg:px-16"
        variants={container}
        initial="hidden"
        animate="visible"
      >
        {/* Part label */}
        <motion.div variants={item} className="mb-3">
          <span
            className="text-[11px] font-black tracking-[0.4em] uppercase"
            style={{ color: 'hsl(41 92% 67%)' }}
          >
            {partNumber}
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          variants={item}
          className="mb-4 text-[64px] font-black leading-[0.88] tracking-tight text-white sm:text-[80px] lg:text-[96px]"
        >
          {title}
        </motion.h1>

        {/* Description */}
        <motion.p
          variants={item}
          className="mb-8 max-w-xl text-base text-white/45 leading-relaxed sm:text-lg"
        >
          {description}
        </motion.p>

        {/* Lesson list */}
        {displayItems.length > 0 && (
          <motion.div variants={item} className="mb-6 max-w-xl">
            <p
              className="mb-3 text-[10px] font-black tracking-[0.25em] uppercase"
              style={{ color: 'rgba(255,255,255,0.25)' }}
            >
              In this chapter
            </p>
            <div className="flex flex-col gap-1.5">
              {displayItems.map((label, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-black"
                    style={{
                      background: 'rgba(247,195,93,0.12)',
                      border: '1px solid rgba(247,195,93,0.25)',
                      color: 'hsl(41 92% 67%)',
                    }}
                  >
                    {i + 1}
                  </span>
                  <span className="text-sm font-medium text-white/60 leading-tight">{label}</span>
                </div>
              ))}
              {overflow > 0 && (
                <div className="flex items-center gap-3">
                  <span
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-black"
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.10)',
                      color: 'rgba(255,255,255,0.25)',
                    }}
                  >
                    +{overflow}
                  </span>
                  <span className="text-xs text-white/30 italic">more</span>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Footer row */}
        <motion.div variants={item} className="flex items-center gap-4">
          <div
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(247,195,93,0.15)',
            }}
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: 'hsl(41 92% 67%)' }}
            />
            <span className="text-white/50">
              {slideCount} {slideCount === 1 ? 'slide' : 'slides'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'rgba(255,255,255,0.22)' }}>
            <span>Press</span>
            <kbd
              className="rounded px-1.5 py-0.5 font-semibold"
              style={{
                background: 'rgba(255,255,255,0.07)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'rgba(255,255,255,0.40)',
                fontSize: 10,
              }}
            >
              →
            </kbd>
            <span>to begin</span>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
