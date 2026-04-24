import { notFound } from 'next/navigation';
import { loadCourse, serializeCourse } from '@/lib/content-loader';
import { PresentationPlayer } from '@/components/codex/PresentationPlayer';

// Known static routes that Next.js may try to resolve through [course]
const RESERVED = new Set(['favicon.ico', 'robots.txt', 'sitemap.xml', '_next']);

interface CoursePageProps {
  params: Promise<{ course: string }>;
}

export default async function CoursePage({ params }: CoursePageProps) {
  const { course: courseSlug } = await params;
  if (RESERVED.has(courseSlug)) notFound();

  try {
    const course = await loadCourse(courseSlug);
    const serialized = serializeCourse(course);
    return <PresentationPlayer course={serialized} courseSlug={courseSlug} />;
  } catch (err) {
    console.error('[CoursePage] loadCourse failed for', courseSlug, err);
    notFound();
  }
}
