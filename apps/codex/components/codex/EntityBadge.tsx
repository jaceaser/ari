import { cn } from '@/lib/cn'
import type { EntityType } from '@/types/codex'
import type { Locale } from '@/lib/translations'
import { getTranslations } from '@/lib/translations'

function getTypeConfig(type: EntityType, locale: Locale): { label: string; className: string } {
  const t = getTranslations(locale)
  const configs: Record<EntityType, { label: string; className: string }> = {
    topic: {
      label: t.topic,
      className: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
    },
    'case-study': {
      label: t.caseStudy,
      className: 'bg-teal-500/20 text-teal-400 border border-teal-500/30',
    },
    pathway: {
      label: t.pathway,
      className: 'bg-purple-500/20 text-purple-400 border border-purple-500/30',
    },
    glossary: {
      label: t.glossaryLabel,
      className: 'bg-slate-500/20 text-slate-300 border border-slate-500/30',
    },
    'operator-card': {
      label: t.operator,
      className: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
    },
    document: {
      label: t.document,
      className: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
    },
    'state-note': {
      label: t.stateNote,
      className: 'bg-green-500/20 text-green-400 border border-green-500/30',
    },
  }
  return configs[type] ?? configs.document
}

interface EntityBadgeProps {
  type: EntityType
  className?: string
  locale?: Locale
}

export function EntityBadge({ type, className, locale = 'en' }: EntityBadgeProps) {
  const config = getTypeConfig(type, locale)
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
  )
}
