import fs from 'fs'
import path from 'path'
import { notFound } from 'next/navigation'
import { loadCourse, serializeCourse } from '@/lib/content-loader'
import { PresentationPlayer } from '@/components/codex/PresentationPlayer'
import type { Locale } from '@/lib/translations'
import { SUPPORTED_LOCALES } from '@/lib/translations'

// Known static routes that Next.js may try to resolve through [course]
const RESERVED = new Set(['favicon.ico', 'robots.txt', 'sitemap.xml', '_next'])

export async function generateStaticParams() {
  const guidesDir = path.join(process.cwd(), 'course-guides')
  const courses = fs.readdirSync(guidesDir).filter(
    (name) =>
      !name.startsWith('.') &&
      fs.statSync(path.join(guidesDir, name)).isDirectory()
  )
  return SUPPORTED_LOCALES.flatMap((locale) =>
    courses.map((course) => ({ locale, course }))
  )
}

interface CoursePageProps {
  params: Promise<{ locale: string; course: string }>
}

export default async function CoursePage({ params }: CoursePageProps) {
  const { locale, course: courseSlug } = await params
  if (RESERVED.has(courseSlug)) notFound()

  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'

  try {
    const course = await loadCourse(courseSlug, safeLocale)
    const serialized = serializeCourse(course)
    return <PresentationPlayer course={serialized} courseSlug={courseSlug} locale={safeLocale} />
  } catch (err) {
    console.error('[CoursePage] loadCourse failed for', courseSlug, err)
    notFound()
  }
}
