import { notFound } from 'next/navigation'
import { loadCourse } from '@/lib/content-loader'
import { BackToCourse } from '@/components/codex/BackToCourse'
import Link from 'next/link'
import type { AppendixSection } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { getTranslations, SUPPORTED_LOCALES } from '@/lib/translations'

interface AppendixPageProps {
  params: Promise<{ locale: string; course: string }>
}

const STATE_LABELS: Record<string, string> = {
  'district-of-columbia': 'District of Columbia',
  'american-samoa': 'American Samoa',
  'northern-mariana-islands': 'Northern Mariana Islands',
  'us-virgin-islands': 'U.S. Virgin Islands',
  'new-hampshire': 'New Hampshire',
  'new-jersey': 'New Jersey',
  'new-mexico': 'New Mexico',
  'new-york': 'New York',
  'north-carolina': 'North Carolina',
  'north-dakota': 'North Dakota',
  'rhode-island': 'Rhode Island',
  'south-carolina': 'South Carolina',
  'south-dakota': 'South Dakota',
  'west-virginia': 'West Virginia',
  'puerto-rico': 'Puerto Rico',
  'guam': 'Guam',
}

function displayTitle(section: AppendixSection): string {
  return STATE_LABELS[section.slug] ?? section.title
}

export default async function AppendixPage({ params }: AppendixPageProps) {
  const { locale, course } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'
  const t = getTranslations(safeLocale)

  const courseData = await loadCourse(course, safeLocale)

  if (!courseData.appendix.size) notFound()

  const intro = Array.from(courseData.appendix.values()).filter((s) => s.category === 'intro')
  const survey = Array.from(courseData.appendix.values()).filter((s) => s.category === 'survey')
  const states = Array.from(courseData.appendix.values())
    .filter((s) => s.category === 'state')
    .sort((a, b) => displayTitle(a).localeCompare(displayTitle(b)))

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} locale={safeLocale} />

      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="mb-10 border-b border-white/[0.06] pb-6">
          <span className="mb-3 inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-400">
            {t.appendix}
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
            {t.appendix}
          </h1>
          <p className="mt-2 text-base text-white/50">
            {t.appendixPageDescription}
          </p>
        </div>

        <div className="space-y-10">
          {/* Overview & Practitioner Notes */}
          {intro.length > 0 && (
            <section>
              <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-white/30">
                {t.overviewNotes}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {intro.map((section) => (
                  <SectionCard key={section.slug} section={section} course={course} locale={safeLocale} displayTitle={displayTitle(section)} />
                ))}
              </div>
            </section>
          )}

          {/* Survey & Summary Tables */}
          {survey.length > 0 && (
            <section>
              <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-white/30">
                {t.stateSurvey}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {survey.map((section) => (
                  <SectionCard key={section.slug} section={section} course={course} locale={safeLocale} displayTitle={displayTitle(section)} />
                ))}
              </div>
            </section>
          )}

          {/* Individual States */}
          {states.length > 0 && (
            <section>
              <h2 className="mb-4 text-xs font-bold uppercase tracking-widest text-white/30">
                {t.stateEntriesCount(states.length)}
              </h2>
              <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {states.map((section) => (
                  <Link
                    key={section.slug}
                    href={`/${safeLocale}/${course}/appendix/${section.slug}`}
                    className="group rounded-lg border border-white/[0.07] bg-white/[0.02] px-4 py-3 text-sm text-white/50 transition-all hover:border-blue-500/30 hover:bg-blue-500/5 hover:text-blue-300"
                  >
                    {displayTitle(section)}
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function SectionCard({
  section,
  course,
  locale,
  displayTitle,
}: {
  section: AppendixSection
  course: string
  locale: Locale
  displayTitle: string
}) {
  return (
    <Link
      href={`/${locale}/${course}/appendix/${section.slug}`}
      className="group rounded-xl border border-white/[0.07] bg-white/[0.03] p-4 transition-all hover:border-blue-500/30 hover:bg-blue-500/5"
    >
      <p className="font-medium text-white/70 transition-colors group-hover:text-blue-300">
        {displayTitle}
      </p>
    </Link>
  )
}
