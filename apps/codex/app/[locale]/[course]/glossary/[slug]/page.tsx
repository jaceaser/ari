import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import type { GlossaryTerm } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { getTranslations, SUPPORTED_LOCALES } from '@/lib/translations'
import Link from 'next/link'

interface GlossaryTermPageProps {
  params: Promise<{ locale: string; course: string; slug: string }>
}

export default async function GlossaryTermPage({ params }: GlossaryTermPageProps) {
  const { locale, course, slug } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'
  const t = getTranslations(safeLocale)

  const courseData = await loadCourse(course, safeLocale)
  const term = courseData.glossary.get(slug) as GlossaryTerm | undefined

  if (!term) notFound()

  const relatedTermEntities = (term.relatedTerms ?? [])
    .map((t) => courseData.glossary.get(t) ?? courseData.allEntities.get(t))
    .filter(Boolean)

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <p className="mb-2 text-xs font-bold tracking-[0.2em] uppercase text-white/30">{t.glossary}</p>
          <h1
            className="text-3xl font-black tracking-tight"
            style={{
              background: 'linear-gradient(135deg, hsl(210, 60%, 70%), hsl(210, 60%, 55%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            {term.title}
          </h1>
        </div>

        <div className="space-y-6">
          <div
            className="rounded-2xl p-6"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(247,195,93,0.2)',
            }}
          >
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-400/60">
              Definition
            </p>
            <p className="text-lg text-white/80">{term.definition}</p>
          </div>

          {term.plainEnglish && (
            <div
              className="rounded-xl p-6"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
            >
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-white/30">
                Plain English
              </p>
              <p className="text-white/70">{term.plainEnglish}</p>
            </div>
          )}

          {term.aliases && term.aliases.length > 0 && (
            <div>
              <p className="mb-2 text-sm text-white/30">Also known as:</p>
              <div className="flex flex-wrap gap-2">
                {term.aliases.map((alias) => (
                  <span
                    key={alias}
                    className="rounded-full bg-white/[0.06] px-3 py-1 text-sm text-white/50"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          )}

          {relatedTermEntities.length > 0 && (
            <div>
              <h2 className="mb-3 text-lg font-semibold text-white/80">Related Terms</h2>
              <div className="flex flex-wrap gap-2">
                {relatedTermEntities.map((related) => (
                  <Link
                    key={related!.id}
                    href={`/${safeLocale}/${course}/glossary/${related!.slug}`}
                    className="rounded-lg border border-slate-500/30 bg-slate-500/10 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-slate-500/50"
                  >
                    {related!.title}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
