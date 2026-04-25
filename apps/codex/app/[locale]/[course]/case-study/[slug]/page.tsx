import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import { RelatedEntities } from '@/components/codex/RelatedEntities'
import { EntityBadge } from '@/components/codex/EntityBadge'
import type { CaseStudy } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { SUPPORTED_LOCALES } from '@/lib/translations'
import Link from 'next/link'

interface CaseStudyPageProps {
  params: Promise<{ locale: string; course: string; slug: string }>
}

export default async function CaseStudyPage({ params }: CaseStudyPageProps) {
  const { locale, course, slug } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'

  const courseData = await loadCourse(course, safeLocale)
  const cs = courseData.caseStudies.get(slug) as CaseStudy | undefined

  if (!cs) notFound()

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <div className="mb-3">
            <EntityBadge type="case-study" locale={safeLocale} />
          </div>
          <h1
            className="text-3xl font-black tracking-tight sm:text-4xl"
            style={{
              background:
                'linear-gradient(135deg, hsl(173, 58%, 60%), hsl(173, 58%, 45%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            {cs.title}
          </h1>
          {cs.summary && <p className="mt-2 text-base text-white/50">{cs.summary}</p>}
        </div>

        <div className="space-y-8">
          {/* Doctrines */}
          {cs.doctrines && cs.doctrines.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-white/30">Doctrines:</span>
              {cs.doctrines.map((doctrine) => {
                const entity = courseData.allEntities.get(doctrine)
                return (
                  <Link
                    key={doctrine}
                    href={`/${safeLocale}/${course}/topic/${doctrine}`}
                    className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-sm text-amber-400 transition-colors hover:border-amber-500/50"
                  >
                    <EntityBadge type="topic" className="text-xs" locale={safeLocale} />
                    {entity?.title ?? doctrine}
                  </Link>
                )
              })}
            </div>
          )}

          {/* Structured sections */}
          <div className="grid gap-6">
            {cs.scenario && (
              <div
                className="rounded-xl p-6"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.07)',
                }}
              >
                <h2 className="mb-3 text-lg font-semibold text-white/80">Scenario</h2>
                <p className="text-white/50">{cs.scenario}</p>
              </div>
            )}
            {cs.play && (
              <div
                className="rounded-xl p-6"
                style={{
                  background: 'rgba(59,178,152,0.05)',
                  border: '1px solid rgba(59,178,152,0.15)',
                }}
              >
                <h2 className="mb-3 text-lg font-semibold text-teal-400">The Play</h2>
                <p className="text-white/50">{cs.play}</p>
              </div>
            )}
            {cs.outcome && (
              <div
                className="rounded-xl p-6"
                style={{
                  background: 'rgba(247,195,93,0.05)',
                  border: '1px solid rgba(247,195,93,0.15)',
                }}
              >
                <h2 className="mb-3 text-lg font-semibold text-amber-400">Outcome</h2>
                <p className="text-white/50">{cs.outcome}</p>
              </div>
            )}
            {cs.takeaway && (
              <div
                className="rounded-xl p-6"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(247,195,93,0.2)',
                  borderLeft: '3px solid hsl(41 92% 67% / 0.7)',
                }}
              >
                <h2 className="mb-3 text-lg font-semibold text-white/80">Takeaway</h2>
                <p className="text-white/60">{cs.takeaway}</p>
              </div>
            )}
          </div>

          {/* Body content */}
          {cs.body && (
            <div
              className="prose prose-invert max-w-none prose-headings:text-white/90 prose-h2:border-b prose-h2:border-white/10 prose-h2:pb-2 prose-p:text-white/50 prose-strong:text-white/80 prose-li:text-white/50"
              dangerouslySetInnerHTML={{ __html: cs.body }}
            />
          )}

          {cs.relatedNodes && cs.relatedNodes.length > 0 && (
            <RelatedEntities
              slugs={cs.relatedNodes}
              course={courseData}
              courseSlug={course}
              locale={safeLocale}
              title="Related Topics"
            />
          )}
        </div>
      </div>
    </div>
  )
}
