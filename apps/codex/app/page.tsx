import { listCourses } from '@/lib/list-courses';
import { CourseCard } from '@/components/codex/CourseCard';

const noiseUrl =
  "data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E";

export default function CatalogPage() {
  const courses = listCourses();

  return (
    <div
      className="relative min-h-dvh bg-[#080808]"
      style={{
        backgroundImage:
          'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(247,195,93,0.07), transparent)',
      }}
    >
      {/* Noise texture */}
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.025]"
        style={{ backgroundImage: `url("${noiseUrl}")` }}
      />

      <div className="relative z-10 mx-auto max-w-4xl px-6 py-16 sm:py-24">
        {/* Header */}
        <div className="mb-14 text-center">
          <p
            className="mb-4 text-[11px] font-black tracking-[0.35em] uppercase"
            style={{ color: 'hsl(41 92% 67%)' }}
          >
            ARI · Codex
          </p>
          <h1 className="mb-4 text-[44px] font-black leading-[0.9] tracking-tight text-white sm:text-[60px]">
            Course Catalog
          </h1>
          <p className="mx-auto max-w-md text-base text-white/40 leading-relaxed">
            Premium interactive courses on real estate investment strategies. Built by REI Labs.
          </p>
        </div>

        {/* Course grid */}
        {courses.length === 0 ? (
          <p className="text-center text-sm text-white/30 italic">No courses available yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            {courses.map((course) => (
              <CourseCard key={course.slug} course={course} />
            ))}
          </div>
        )}

        <p className="mt-16 text-center text-[11px] tracking-[0.2em] uppercase text-white/20">
          Powered by REI Labs
        </p>
      </div>
    </div>
  );
}
