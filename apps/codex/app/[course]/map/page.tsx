import { loadCourse } from '@/lib/content-loader';
import { buildGraph } from '@/lib/graph-builder';
import { MapClient } from './MapClient';
import { BackToCourse } from '@/components/codex/BackToCourse';

interface MapPageProps {
  params: Promise<{ course: string }>;
}

export default async function MapPage({ params }: MapPageProps) {
  const { course } = await params;
  const courseData = await loadCourse(course);
  const { nodes, edges } = buildGraph(courseData);

  return (
    <div className="flex h-screen flex-col bg-[#060608]">
      <BackToCourse courseSlug={course} courseTitle={courseData.config.title} />

      <div className="relative flex-1">
        {/* Instructions */}
        <div className="pointer-events-none absolute left-1/2 top-4 z-10 -translate-x-1/2">
          <div
            className="flex items-center gap-2 rounded-full px-4 py-2 text-sm backdrop-blur-sm"
            style={{
              background: 'rgba(6,6,8,0.85)',
              border: '1px solid rgba(247,195,93,0.2)',
              color: 'rgba(255,255,255,0.5)',
            }}
          >
            <span style={{ color: 'hsl(41 92% 67%)' }}>⬡</span>
            Click any node to explore · Scroll to zoom · Drag to pan
          </div>
        </div>

        <MapClient
          graphNodes={nodes}
          graphEdges={edges}
          courseSlug={course}
        />
      </div>
    </div>
  );
}
