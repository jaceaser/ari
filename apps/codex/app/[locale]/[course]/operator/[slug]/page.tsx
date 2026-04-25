import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import type { OperatorCard } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { getTranslations, SUPPORTED_LOCALES } from '@/lib/translations'
import { RelatedEntities } from '@/components/codex/RelatedEntities'
import { InteractiveChecklist } from './InteractiveChecklist'
import { EntityBadge } from '@/components/codex/EntityBadge'
import { AlertTriangle } from 'lucide-react'

interface OperatorPageProps {
  params: Promise<{ locale: string; course: string; slug: string }>
}

export default async function OperatorPage({ params }: OperatorPageProps) {
  const { locale, course, slug } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'
  const t = getTranslations(safeLocale)

  const courseData = await loadCourse(course, safeLocale)
  const card = courseData.operatorCards.get(slug) as OperatorCard | undefined

  if (!card) notFound()

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <div className="mb-3">
            <EntityBadge type="operator-card" locale={safeLocale} />
          </div>
          <h1
            className="text-3xl font-black tracking-tight"
            style={{
              background: 'linear-gradient(135deg, hsl(25, 90%, 70%), hsl(25, 90%, 55%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            {card.title}
          </h1>
          {card.summary && <p className="mt-2 text-base text-white/50">{card.summary}</p>}
        </div>

        <div className="space-y-8">
          {card.checklist && card.checklist.length > 0 && (
            <div
              className="rounded-xl p-6"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
            >
              <h2 className="mb-4 text-xl font-semibold text-white/80">{t.checklist}</h2>
              <InteractiveChecklist items={card.checklist} cardId={card.id} />
            </div>
          )}

          {card.commonMistakes && card.commonMistakes.length > 0 && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-red-400">
                <AlertTriangle className="h-5 w-5" />
                {t.commonMistakes}
              </h2>
              <ul className="space-y-3">
                {card.commonMistakes.map((mistake, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-red-300/70">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                    {mistake}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {card.scripts && card.scripts.length > 0 && (
            <div
              className="rounded-xl p-6"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
            >
              <h2 className="mb-4 text-xl font-semibold text-white/80">Scripts</h2>
              <div className="space-y-4">
                {card.scripts.map((script, i) => (
                  <div
                    key={i}
                    className="rounded-lg p-4 font-mono text-sm text-white/60"
                    style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)' }}
                  >
                    {script}
                  </div>
                ))}
              </div>
            </div>
          )}

          {card.relatedNodes && card.relatedNodes.length > 0 && (
            <RelatedEntities
              slugs={card.relatedNodes}
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
