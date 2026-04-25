import Link from 'next/link'
import { LanguageSwitcher } from './LanguageSwitcher'
import type { Locale } from '@/lib/translations'
import { getTranslations } from '@/lib/translations'

interface BackToCourseProps {
  courseSlug: string
  courseTitle: string
  locale?: Locale
}

export function BackToCourse({ courseSlug, courseTitle, locale = 'en' }: BackToCourseProps) {
  const t = getTranslations(locale)

  return (
    <header
      className="sticky top-0 z-40 flex items-center gap-3 border-b px-4 py-3 sm:px-6"
      style={{
        background: 'rgba(8,8,8,0.95)',
        backdropFilter: 'blur(12px)',
        borderColor: 'rgba(255,255,255,0.06)',
      }}
    >
      <Link
        href={`/${locale}/${courseSlug}`}
        className="group flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-all"
        style={{ color: 'rgba(255,255,255,0.4)' }}
      >
        <svg
          className="h-4 w-4 transition-transform group-hover:-translate-x-0.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        <span className="group-hover:text-white transition-colors">{t.backToCourse(courseTitle)}</span>
      </Link>

      <div className="ml-auto flex items-center gap-3">
        <Link
          href={`/${locale}/${courseSlug}/appendix`}
          className="rounded-md px-2.5 py-1 text-xs font-medium text-white/35 transition-colors hover:text-blue-300"
        >
          {t.appendix}
        </Link>
        <LanguageSwitcher />
        <span
          className="text-xs font-bold tracking-[0.2em] uppercase"
          style={{ color: 'hsl(41 92% 67%)' }}
        >
          ARI
        </span>
        <span className="text-xs text-white/20">·</span>
        <span className="text-xs tracking-wider uppercase text-white/30">CODEX</span>
      </div>
    </header>
  )
}
