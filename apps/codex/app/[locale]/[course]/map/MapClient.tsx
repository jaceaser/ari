'use client';

import { useState } from 'react';
import { KnowledgeMap } from '@/components/codex/KnowledgeMap';
import type { GraphNode, GraphEdge } from '@/lib/graph-builder';
import type { EntityType } from '@/types/codex';

const allTypes: EntityType[] = ['topic', 'case-study', 'pathway', 'glossary', 'operator-card'];

const typeLabels: Record<EntityType, string> = {
  topic: 'Topics',
  'case-study': 'Case Studies',
  pathway: 'Pathways',
  glossary: 'Glossary',
  'operator-card': 'Operator',
  document: 'Documents',
  'state-note': 'State Notes',
};

const typeColors: Partial<Record<EntityType, string>> = {
  topic: 'rgb(247, 195, 93)',
  'case-study': 'rgb(45, 212, 191)',
  pathway: 'rgb(167, 139, 250)',
  glossary: 'rgb(148, 163, 184)',
  'operator-card': 'rgb(251, 146, 60)',
};

interface MapClientProps {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  courseSlug: string;
}

export function MapClient({ graphNodes, graphEdges, courseSlug }: MapClientProps) {
  const [activeTypes, setActiveTypes] = useState<EntityType[]>([]);

  const toggleType = (type: EntityType) => {
    setActiveTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  return (
    <div className="relative flex h-full flex-col">
      {/* Filter bar */}
      <div className="flex items-center gap-2 border-b border-[var(--border)] bg-[hsl(0_0%_5%/0.95)] px-4 py-2.5 backdrop-blur-sm">
        <span className="text-xs font-medium text-[var(--muted-foreground)]">Filter:</span>
        {allTypes.map((type) => {
          const active = activeTypes.includes(type);
          const color = typeColors[type];
          return (
            <button
              key={type}
              type="button"
              onClick={() => toggleType(type)}
              className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all"
              style={{
                border: `1px solid ${color ? `${color}${active ? '' : '44'}` : '#333'}`,
                backgroundColor: active ? `${color}22` : 'transparent',
                color: active ? color : '#666',
              }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: color ?? '#666', opacity: active ? 1 : 0.4 }}
              />
              {typeLabels[type]}
            </button>
          );
        })}
        {activeTypes.length > 0 && (
          <button
            type="button"
            onClick={() => setActiveTypes([])}
            className="ml-2 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            Clear
          </button>
        )}
      </div>

      {/* Map */}
      <div className="flex-1">
        <KnowledgeMap
          graphNodes={graphNodes}
          graphEdges={graphEdges}
          courseSlug={courseSlug}
          activeTypes={activeTypes.length > 0 ? activeTypes : undefined}
        />
      </div>
    </div>
  );
}
