import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import { RelatedEntities } from '@/components/codex/RelatedEntities'
import { EntityBadge } from '@/components/codex/EntityBadge'
import type { Topic } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { getTranslations, SUPPORTED_LOCALES } from '@/lib/translations'
import { AlertTriangle, Clock, ChevronRight } from 'lucide-react'
import Link from 'next/link'
import { BookmarkToggle } from './BookmarkToggle'

interface TopicPageProps {
  params: Promise<{ locale: string; course: string; slug: string }>
}

export default async function TopicPage({ params }: TopicPageProps) {
  const { locale, course, slug } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'
  const t = getTranslations(safeLocale)

  const courseData = await loadCourse(course, safeLocale)
  const topic = courseData.topics.get(slug) as Topic | undefined

  if (!topic) notFound()

  const difficultyColors = {
    beginner: 'text-green-400 bg-green-400/10 border-green-400/20',
    intermediate: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
    advanced: 'text-red-400 bg-red-400/10 border-red-400/20',
  }

  const difficultyLabels: Record<string, string> = {
    beginner: t.beginner,
    intermediate: t.intermediate,
    advanced: t.advanced,
  }

  const relatedCaseStudies = Array.from(courseData.caseStudies.values()).filter(
    (cs) => cs.doctrines?.includes(slug) || cs.relatedNodes?.includes(slug)
  )

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="mt-4 grid gap-8 lg:grid-cols-[1fr_280px]">
          {/* Main content */}
          <div className="min-w-0 space-y-8">
            {/* Header */}
            <div className="border-b border-white/[0.06] pb-6">
              <div className="mb-3">
                <EntityBadge type="topic" locale={safeLocale} />
              </div>
              <h1
                className="text-3xl font-black tracking-tight sm:text-4xl"
                style={{
                  background:
                    'linear-gradient(135deg, hsl(41, 92%, 75%), hsl(41, 92%, 60%), hsl(38, 85%, 50%))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                {topic.title}
              </h1>
              {topic.summary && (
                <p className="mt-2 text-base text-white/50">{topic.summary}</p>
              )}
            </div>

            {/* Plain English box */}
            {topic.plainEnglish && (
              <div
                className="rounded-2xl p-6"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(247,195,93,0.2)',
                  borderLeft: '3px solid hsl(41 92% 67% / 0.7)',
                }}
              >
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-amber-400/60">
                  Plain English
                </p>
                <p className="text-lg font-medium text-white/80">
                  {topic.plainEnglish}
                </p>
              </div>
            )}

            {topic.whyItMatters && (
              <div>
                <h2 className="mb-3 text-xl font-semibold text-white/90">Why It Matters</h2>
                <p className="text-white/50">{topic.whyItMatters}</p>
              </div>
            )}

            {topic.whenUsed && (
              <div>
                <h2 className="mb-3 text-xl font-semibold text-white/90">When It&apos;s Used</h2>
                <p className="text-white/50">{topic.whenUsed}</p>
              </div>
            )}

            {topic.prerequisites && topic.prerequisites.length > 0 && (
              <div>
                <h2 className="mb-3 text-xl font-semibold text-white/90">Prerequisites</h2>
                <div className="flex flex-wrap gap-2">
                  {topic.prerequisites.map((prereq) => {
                    const prereqEntity = courseData.allEntities.get(prereq)
                    return (
                      <Link
                        key={prereq}
                        href={`/${safeLocale}/${course}/topic/${prereq}`}
                        className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-white/60 transition-colors hover:border-amber-500/40 hover:text-amber-400"
                      >
                        {prereqEntity?.title ?? prereq}
                        <ChevronRight className="h-3 w-3" />
                      </Link>
                    )
                  })}
                </div>
              </div>
            )}

            {topic.risks && topic.risks.length > 0 && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-5">
                <h2 className="mb-3 flex items-center gap-2 text-xl font-semibold text-red-400">
                  <AlertTriangle className="h-5 w-5" />
                  Risks &amp; Red Flags
                </h2>
                <ul className="space-y-2">
                  {topic.risks.map((risk, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-red-300/70">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {topic.body && (
              <div
                className="prose prose-invert max-w-none prose-headings:text-white/90 prose-p:text-white/50 prose-strong:text-white/80 prose-li:text-white/50"
                dangerouslySetInnerHTML={{ __html: topic.body }}
              />
            )}

            {topic.operatorNotes && (
              <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-5">
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-purple-400">
                  Operator Notes
                </h2>
                <p className="text-sm text-purple-300/80">{topic.operatorNotes}</p>
              </div>
            )}

            {topic.nextSteps && topic.nextSteps.length > 0 && (
              <div>
                <h2 className="mb-3 text-xl font-semibold text-white/90">Next Steps</h2>
                <div className="flex flex-wrap gap-2">
                  {topic.nextSteps.map((next) => {
                    const nextEntity = courseData.allEntities.get(next)
                    return (
                      <Link
                        key={next}
                        href={`/${safeLocale}/${course}/topic/${next}`}
                        className="flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-sm font-medium text-amber-400 transition-all hover:border-amber-500/50 hover:bg-amber-500/15"
                      >
                        {nextEntity?.title ?? next}
                        <ChevronRight className="h-3 w-3" />
                      </Link>
                    )
                  })}
                </div>
              </div>
            )}

            {relatedCaseStudies.length > 0 && (
              <div>
                <h2 className="mb-4 text-xl font-semibold text-white/90">Case Studies</h2>
                <div className="grid gap-4 sm:grid-cols-2">
                  {relatedCaseStudies.map((cs) => (
                    <Link
                      key={cs.id}
                      href={`/${safeLocale}/${course}/case-study/${cs.slug}`}
                      className="group rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition-all hover:border-teal-500/40"
                    >
                      <div className="mb-2">
                        <EntityBadge type="case-study" locale={safeLocale} />
                      </div>
                      <p className="font-medium text-white/80 transition-colors group-hover:text-teal-400">
                        {cs.title}
                      </p>
                      <p className="mt-1 line-clamp-2 text-sm text-white/40">
                        {cs.summary}
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {topic.relatedNodes && topic.relatedNodes.length > 0 && (
              <RelatedEntities
                slugs={topic.relatedNodes}
                course={courseData}
                courseSlug={course}
                locale={safeLocale}
                title="Related Concepts"
              />
            )}
          </div>

          {/* Sidebar */}
          <aside className="space-y-4">
            <div
              className="rounded-xl p-5"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
            >
              <div className="space-y-4">
                {topic.estimatedReadTime && (
                  <div className="flex items-center gap-2 text-sm text-white/40">
                    <Clock className="h-4 w-4" />
                    {topic.estimatedReadTime} min read
                  </div>
                )}
                {topic.difficultyLevel && (
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-white/30">Difficulty</p>
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${difficultyColors[topic.difficultyLevel]}`}
                    >
                      {difficultyLabels[topic.difficultyLevel] ?? topic.difficultyLevel}
                    </span>
                  </div>
                )}
                {topic.tags && topic.tags.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-xs font-medium text-white/30">Tags</p>
                    <div className="flex flex-wrap gap-1.5">
                      {topic.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full bg-white/[0.06] px-2 py-0.5 text-xs text-white/40"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <BookmarkToggle entityId={topic.id} />
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
