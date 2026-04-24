import { loadCourse } from '@/lib/content-loader';
import { BackToCourse } from '@/components/codex/BackToCourse';
import Link from 'next/link';
import type { GlossaryTerm } from '@/types/codex';

interface GlossaryPageProps {
  params: Promise<{ course: string }>;
}

export default async function GlossaryPage({ params }: GlossaryPageProps) {
  const { course } = await params;
  const courseData = await loadCourse(course);

  const terms = Array.from(courseData.glossary.values()).sort((a, b) =>
    a.title.localeCompare(b.title)
  );

  const groups = new Map<string, GlossaryTerm[]>();
  for (const term of terms) {
    const letter = term.title[0].toUpperCase();
    if (!groups.has(letter)) groups.set(letter, []);
    groups.get(letter)!.push(term);
  }

  const sortedLetters = Array.from(groups.keys()).sort();

  return (
    <div className="min-h-screen bg-[#080808]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} />

      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="mb-8 border-b border-white/[0.06] pb-6">
          <h1
            className="text-3xl font-black tracking-tight"
            style={{
              background: 'linear-gradient(135deg, hsl(41, 92%, 75%), hsl(41, 92%, 60%))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Glossary
          </h1>
          <p className="mt-1 text-white/40">{terms.length} terms defined</p>
        </div>

        {/* Letter anchors */}
        <div className="mb-6 flex flex-wrap gap-2">
          {sortedLetters.map((letter) => (
            <a
              key={letter}
              href={`#letter-${letter}`}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-medium text-white/40 transition-colors hover:text-amber-400"
              style={{ border: '1px solid rgba(255,255,255,0.08)' }}
            >
              {letter}
            </a>
          ))}
        </div>

        <div className="space-y-10">
          {sortedLetters.map((letter) => (
            <section key={letter} id={`letter-${letter}`}>
              <h2
                className="mb-4 text-2xl font-bold"
                style={{ color: 'hsl(41 92% 67%)' }}
              >
                {letter}
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {groups.get(letter)!.map((term) => (
                  <Link
                    key={term.id}
                    href={`/${course}/glossary/${term.slug}`}
                    className="group block rounded-xl p-4 transition-all"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.07)',
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLAnchorElement).style.borderColor =
                        'rgba(148,163,184,0.3)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLAnchorElement).style.borderColor =
                        'rgba(255,255,255,0.07)';
                    }}
                  >
                    <h3 className="font-semibold text-white/80 transition-colors group-hover:text-slate-300">
                      {term.title}
                    </h3>
                    {term.plainEnglish && (
                      <p className="mt-1 line-clamp-2 text-sm text-white/40">
                        {term.plainEnglish}
                      </p>
                    )}
                    {!term.plainEnglish && term.definition && (
                      <p className="mt-1 line-clamp-2 text-sm text-white/40">
                        {term.definition}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
