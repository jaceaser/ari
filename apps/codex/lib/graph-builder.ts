import type { Course, CodexEntity, EntityType, Topic } from '@/types/codex';

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  slug: string;
  featured: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
}

export function buildGraph(course: Course): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = [];
  const edgeSet = new Set<string>();
  const edges: GraphEdge[] = [];

  function addNode(entity: CodexEntity) {
    nodes.push({
      id: entity.id,
      label: entity.title,
      type: entity.type,
      slug: entity.slug,
      featured: entity.featured ?? false,
    });
  }

  function addEdge(source: string, target: string, label: string) {
    if (!source || !target || source === target) return;
    const key = `${source}--${target}`;
    const reverseKey = `${target}--${source}`;
    if (edgeSet.has(key) || edgeSet.has(reverseKey)) return;
    edgeSet.add(key);
    edges.push({ id: key, source, target, label });
  }

  for (const entity of course.allEntities.values()) {
    addNode(entity);

    for (const related of entity.relatedNodes ?? []) {
      addEdge(entity.id, related, 'related');
    }

    for (const prereq of entity.prerequisites ?? []) {
      addEdge(prereq, entity.id, 'prerequisite');
    }

    if (entity.type === 'topic') {
      const topic = entity as Topic;
      for (const next of topic.nextSteps ?? []) {
        addEdge(entity.id, next, 'next');
      }
    }
  }

  return { nodes, edges };
}
