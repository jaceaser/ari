import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import { PathwaySteps } from '@/components/codex/PathwaySteps'
import { RelatedEntities } from '@/components/codex/RelatedEntities'
import { EntityBadge } from '@/components/codex/EntityBadge'
import type { Pathway } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { SUPPORTED_LOCALES } from '@/lib/translations'
import { MapPin, FileText, AlertCircle } from 'lucide-react'

interface PathwayPageProps {
  params: Promise<{ locale: string; course: string; slug: string }>
}

export default async function PathwayPage({ params }: PathwayPageProps) {
  const { locale, course, slug } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'

  const courseData = await loadCourse(course, safeLocale)
  const pathway = courseData.pathways.get(slug) as Pathway | undefined

  if (!pathway) notFound()

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {/* Header */}
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <div className="mb-3">
            <EntityBadge type="pathway" locale={safeLocale} />
          </div>
          <h1
            className="text-3xl font-black tracking-tight sm:text-4xl"
            style={{
              background:
                'linear-gradient(135deg, hsl(270, 60%, 75%), hsl(270, 60%, 60%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            {pathway.title}
          </h1>
          {pathway.summary && (
            <p className="mt-2 text-base text-white/50">{pathway.summary}</p>
          )}
        </div>

        <div className="space-y-8">
          {pathway.entryCondition && (
            <div
              className="flex items-start gap-4 rounded-xl p-6"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(247,195,93,0.2)',
              }}
            >
              <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
              <div>
                <p className="mb-1 text-sm font-semibold uppercase tracking-wider text-amber-400/70">
                  Entry Condition
                </p>
                <p className="text-white/70">{pathway.entryCondition}</p>
              </div>
            </div>
          )}

          <div>
            <h2 className="mb-6 text-2xl font-semibold text-white/90">Pathway Steps</h2>
            <PathwaySteps pathway={pathway} courseSlug={course} locale={safeLocale} />
          </div>

          {pathway.likelyDocuments && pathway.likelyDocuments.length > 0 && (
            <div
              className="rounded-xl p-6"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
            >
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white/80">
                <FileText className="h-5 w-5 text-blue-400" />
                Likely Documents
              </h2>
              <div className="flex flex-wrap gap-2">
                {pathway.likelyDocuments.map((doc) => (
                  <span
                    key={doc}
                    className="rounded-lg border border-blue-500/20 bg-blue-500/10 px-3 py-1 text-sm text-blue-400"
                  >
                    {doc}
                  </span>
                ))}
              </div>
            </div>
          )}

          {pathway.stateSensitivity && (
            <div className="flex items-start gap-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-6">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
              <div>
                <p className="mb-1 text-sm font-semibold text-amber-400">State Sensitivity</p>
                <p className="text-sm text-amber-300/70">{pathway.stateSensitivity}</p>
              </div>
            </div>
          )}

          {pathway.relatedNodes && pathway.relatedNodes.length > 0 && (
            <RelatedEntities
              slugs={pathway.relatedNodes}
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
