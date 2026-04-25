import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import Link from 'next/link'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Locale } from '@/lib/translations'
import { getTranslations, SUPPORTED_LOCALES } from '@/lib/translations'

interface AppendixSectionPageProps {
  params: Promise<{ locale: string; course: string; slug: string }>
}

export default async function AppendixSectionPage({ params }: AppendixSectionPageProps) {
  const { locale, course, slug } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'
  const t = getTranslations(safeLocale)

  const courseData = await loadCourse(course, safeLocale)
  const section = courseData.appendix.get(slug)

  if (!section) notFound()

  const allSections = Array.from(courseData.appendix.values())
  const currentIndex = allSections.findIndex((s) => s.slug === slug)
  const prev = currentIndex > 0 ? allSections[currentIndex - 1] : null
  const next = currentIndex < allSections.length - 1 ? allSections[currentIndex + 1] : null

  const categoryLabel =
    section.category === 'state'
      ? 'State Entry'
      : section.category === 'survey'
      ? 'Survey'
      : 'Overview'

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-sm text-white/30">
          <Link href={`/${safeLocale}/${course}/appendix`} className="hover:text-white/60 transition-colors">
            {t.appendix}
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-white/50">{section.title}</span>
        </div>

        {/* Header */}
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <span className="mb-3 inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-400">
            {categoryLabel}
          </span>
          <h1
            className="text-3xl font-black tracking-tight sm:text-4xl"
            style={{
              background: 'linear-gradient(135deg, hsl(215, 70%, 70%), hsl(215, 60%, 55%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            {section.title}
          </h1>
        </div>

        {/* Body */}
        <div
          className="prose prose-invert max-w-none prose-headings:text-white/90 prose-p:text-white/55 prose-strong:text-white/80 prose-li:text-white/55 prose-table:text-sm prose-th:text-white/70 prose-th:font-semibold prose-td:text-white/50 prose-td:border-white/10 prose-th:border-white/10"
          dangerouslySetInnerHTML={{ __html: section.body }}
        />

        {/* Prev/Next */}
        <div className="mt-12 flex items-center justify-between border-t border-white/[0.06] pt-6">
          {prev ? (
            <Link
              href={`/${safeLocale}/${course}/appendix/${prev.slug}`}
              className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white/50 transition-all hover:border-blue-500/30 hover:text-blue-300"
            >
              <ChevronLeft className="h-4 w-4" />
              {prev.title}
            </Link>
          ) : (
            <div />
          )}
          {next ? (
            <Link
              href={`/${safeLocale}/${course}/appendix/${next.slug}`}
              className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm text-white/50 transition-all hover:border-blue-500/30 hover:text-blue-300"
            >
              {next.title}
              <ChevronRight className="h-4 w-4" />
            </Link>
          ) : (
            <div />
          )}
        </div>
      </div>
    </div>
  )
}
