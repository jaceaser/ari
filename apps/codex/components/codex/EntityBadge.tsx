import { cn } from '@/lib/cn';
import type { EntityType } from '@/types/codex';

const typeConfig: Record<EntityType, { label: string; className: string }> = {
  topic: {
    label: 'Topic',
    className: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  },
  'case-study': {
    label: 'Case Study',
    className: 'bg-teal-500/20 text-teal-400 border border-teal-500/30',
  },
  pathway: {
    label: 'Pathway',
    className: 'bg-purple-500/20 text-purple-400 border border-purple-500/30',
  },
  glossary: {
    label: 'Glossary',
    className: 'bg-slate-500/20 text-slate-300 border border-slate-500/30',
  },
  'operator-card': {
    label: 'Operator',
    className: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  },
  document: {
    label: 'Document',
    className: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  },
  'state-note': {
    label: 'State Note',
    className: 'bg-green-500/20 text-green-400 border border-green-500/30',
  },
};

interface EntityBadgeProps {
  type: EntityType;
  className?: string;
}

export function EntityBadge({ type, className }: EntityBadgeProps) {
  const config = typeConfig[type] ?? typeConfig.document;
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  );
}
