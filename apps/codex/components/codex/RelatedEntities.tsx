import type { Course } from '@/types/codex';
import { TopicCard } from './TopicCard';

interface RelatedEntitiesProps {
  slugs: string[];
  course: Course;
  courseSlug: string;
  title: string;
}

export function RelatedEntities({ slugs, course, courseSlug, title }: RelatedEntitiesProps) {
  const entities = slugs
    .map((slug) => course.allEntities.get(slug))
    .filter(Boolean);

  if (entities.length === 0) return null;

  return (
    <div>
      <h2 className="mb-4 text-xl font-semibold text-[var(--foreground)]">{title}</h2>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {entities.map((entity) => (
          <div key={entity!.id} className="w-64 shrink-0">
            <TopicCard entity={entity!} courseSlug={courseSlug} />
          </div>
        ))}
      </div>
    </div>
  );
}
