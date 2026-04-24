import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import type { CodexEntity } from '@/types/codex';
import { EntityBadge } from './EntityBadge';
import { cn } from '@/lib/cn';

interface TopicCardProps {
  entity: CodexEntity;
  courseSlug: string;
  className?: string;
}

function getEntityPath(entity: CodexEntity, courseSlug: string): string {
  const typeMap: Record<string, string> = {
    topic: 'topic',
    'case-study': 'case-study',
    pathway: 'pathway',
    glossary: 'glossary',
    'operator-card': 'operator',
    document: 'document',
    'state-note': 'state-note',
  };
  const segment = typeMap[entity.type] ?? entity.type;
  return `/${courseSlug}/${segment}/${entity.slug}`;
}

export function TopicCard({ entity, courseSlug, className }: TopicCardProps) {
  const href = getEntityPath(entity, courseSlug);

  return (
    <Link href={href} className={cn('group block', className)}>
      <div className="h-full rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-[hsl(var(--ari-gold-hsl))/0.4] hover:shadow-lg hover:shadow-black/20">
        <div className="mb-3 flex items-center justify-between">
          <EntityBadge type={entity.type} />
          {entity.featured && (
            <span className="text-xs text-amber-400/60">Featured</span>
          )}
        </div>
        <h3 className="mb-2 font-semibold text-[var(--card-foreground)] group-hover:text-[hsl(var(--ari-gold-hsl))] transition-colors">
          {entity.title}
        </h3>
        <p className="line-clamp-2 text-sm text-[var(--muted-foreground)]">
          {entity.summary}
        </p>
        <div className="mt-4 flex items-center gap-1 text-xs font-medium text-[hsl(var(--ari-gold-hsl))] opacity-0 transition-opacity group-hover:opacity-100">
          Explore <ArrowRight className="h-3 w-3" />
        </div>
      </div>
    </Link>
  );
}
