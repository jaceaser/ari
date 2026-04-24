'use client';

import { useState, useMemo } from 'react';
import { KnowledgeMap } from '@/components/codex/KnowledgeMap';
import { buildGraph } from '@/lib/graph-builder';
import type { SerializedCourse } from '@/types/codex';
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

interface MapSlideProps {
  course: SerializedCourse;
  courseSlug: string;
}

export function MapSlide({ course, courseSlug }: MapSlideProps) {
  const [activeTypes, setActiveTypes] = useState<EntityType[]>([]);

  // Convert SerializedCourse to a Course-like object for buildGraph
  const courseForGraph = useMemo(
    () => ({
      config: course.config,
      overview: course.overview,
      topics: new Map(course.topics.map((t) => [t.slug, t])),
      caseStudies: new Map(course.caseStudies.map((c) => [c.slug, c])),
      pathways: new Map(course.pathways.map((p) => [p.slug, p])),
      operatorCards: new Map(course.operatorCards.map((o) => [o.slug, o])),
      glossary: new Map(course.glossary.map((g) => [g.slug, g])),
      allEntities: new Map(Object.entries(course.allEntities)),
    }),
    [course]
  );

  const { nodes, edges } = useMemo(() => buildGraph(courseForGraph), [courseForGraph]);

  const toggleType = (type: EntityType) => {
    setActiveTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  return (
    <div className="relative flex h-full w-full flex-col overflow-hidden bg-[#060608]">
      {/* Filter bar */}
      <div
        className="flex shrink-0 items-center gap-2 border-b px-4 py-2.5"
        style={{
          background: 'rgba(6,6,8,0.95)',
          borderColor: 'rgba(255,255,255,0.06)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <span
          className="text-[10px] font-bold tracking-[0.2em] uppercase"
          style={{ color: 'hsl(41 92% 67%)' }}
        >
          Filter:
        </span>
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
                color: active ? color : '#555',
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
            className="ml-2 text-xs transition-colors"
            style={{ color: '#555' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#999')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#555')}
          >
            Clear
          </button>
        )}

        {/* Title */}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-white/20">
            Knowledge Map
          </span>
          <span className="text-xs text-white/20">·</span>
          <span className="text-xs text-white/20">Click any node to explore</span>
        </div>
      </div>

      {/* Map */}
      <div className="flex-1">
        <KnowledgeMap
          graphNodes={nodes}
          graphEdges={edges}
          courseSlug={courseSlug}
          activeTypes={activeTypes.length > 0 ? activeTypes : undefined}
        />
      </div>
    </div>
  );
}
