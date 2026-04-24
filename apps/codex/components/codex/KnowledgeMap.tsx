'use client';

import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useRouter } from 'next/navigation';
import type { GraphNode, GraphEdge } from '@/lib/graph-builder';
import type { EntityType } from '@/types/codex';

const typeColors: Record<EntityType, string> = {
  topic: '#f7c35d',
  'case-study': '#2dd4bf',
  pathway: '#a78bfa',
  glossary: '#94a3b8',
  'operator-card': '#fb923c',
  document: '#60a5fa',
  'state-note': '#4ade80',
};

const typeBgColors: Record<EntityType, string> = {
  topic: 'rgba(247, 195, 93, 0.15)',
  'case-study': 'rgba(45, 212, 191, 0.15)',
  pathway: 'rgba(167, 139, 250, 0.15)',
  glossary: 'rgba(148, 163, 184, 0.15)',
  'operator-card': 'rgba(251, 146, 60, 0.15)',
  document: 'rgba(96, 165, 250, 0.15)',
  'state-note': 'rgba(74, 222, 128, 0.15)',
};

interface CodexNodeData {
  label: string;
  type: EntityType;
  slug: string;
  courseSlug: string;
  featured: boolean;
  [key: string]: unknown;
}

function CodexNode({ data }: { data: CodexNodeData }) {
  const color = typeColors[data.type] ?? '#94a3b8';
  const bg = typeBgColors[data.type] ?? 'rgba(148, 163, 184, 0.15)';

  return (
    <div
      style={{
        background: bg,
        border: `2px solid ${color}${data.featured ? '' : '66'}`,
        borderRadius: 8,
        padding: '6px 12px',
        minWidth: 120,
        maxWidth: 160,
        cursor: 'pointer',
        boxShadow: data.featured ? `0 0 12px ${color}40` : 'none',
        transition: 'all 0.2s',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color,
          marginBottom: 2,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          opacity: 0.7,
        }}
      >
        {data.type}
      </div>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: '#f0f0f0',
          lineHeight: 1.3,
          wordBreak: 'break-word',
        }}
      >
        {data.label}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes: NodeTypes = { codex: CodexNode };

function layoutNodes(graphNodes: GraphNode[]): Node[] {
  const byType = new Map<EntityType, GraphNode[]>();
  for (const node of graphNodes) {
    if (!byType.has(node.type)) byType.set(node.type, []);
    byType.get(node.type)!.push(node);
  }

  const typeLayouts: Record<string, { cx: number; cy: number; r: number }> = {
    topic: { cx: 500, cy: 400, r: 280 },
    'case-study': { cx: 500, cy: 400, r: 500 },
    pathway: { cx: 500, cy: 150, r: 200 },
    glossary: { cx: 500, cy: 700, r: 350 },
    'operator-card': { cx: 120, cy: 400, r: 80 },
    document: { cx: 880, cy: 400, r: 80 },
    'state-note': { cx: 500, cy: 900, r: 80 },
  };

  const nodes: Node[] = [];

  for (const [type, items] of byType.entries()) {
    const layout = typeLayouts[type] ?? { cx: 500, cy: 400, r: 300 };
    const angleStep = (2 * Math.PI) / Math.max(items.length, 1);
    const offset = type === 'pathway' ? -Math.PI / 2 : 0;

    items.forEach((node, i) => {
      const angle = i * angleStep + offset;
      const x = layout.cx + layout.r * Math.cos(angle) - 70;
      const y = layout.cy + layout.r * Math.sin(angle) - 25;
      nodes.push({
        id: node.id,
        type: 'codex',
        position: { x, y },
        data: {
          label: node.label,
          type: node.type,
          slug: node.slug,
          courseSlug: '',
          featured: node.featured,
        } as CodexNodeData,
      });
    });
  }

  return nodes;
}

interface KnowledgeMapProps {
  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  courseSlug: string;
  activeTypes?: EntityType[];
}

export function KnowledgeMap({ graphNodes, graphEdges, courseSlug, activeTypes }: KnowledgeMapProps) {
  const router = useRouter();

  const filteredNodes = useMemo(
    () => (activeTypes && activeTypes.length > 0
      ? graphNodes.filter((n) => activeTypes.includes(n.type))
      : graphNodes),
    [graphNodes, activeTypes]
  );

  const filteredNodeIds = useMemo(
    () => new Set(filteredNodes.map((n) => n.id)),
    [filteredNodes]
  );

  const filteredEdges = useMemo(
    () => graphEdges.filter(
      (e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target)
    ),
    [graphEdges, filteredNodeIds]
  );

  const initialNodes: Node[] = useMemo(() => {
    const laid = layoutNodes(filteredNodes);
    return laid.map((n) => ({
      ...n,
      data: { ...n.data as Record<string, unknown>, courseSlug },
    }));
  }, [filteredNodes, courseSlug]);

  const initialEdges: Edge[] = useMemo(
    () =>
      filteredEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        animated: false,
        style: { stroke: 'rgba(247, 195, 93, 0.25)', strokeWidth: 1.5 },
        labelStyle: { fontSize: 10, fill: '#666' },
        type: 'smoothstep',
      })),
    [filteredEdges]
  );

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const data = node.data as CodexNodeData;
      const typeMap: Record<string, string> = {
        topic: 'topic',
        'case-study': 'case-study',
        pathway: 'pathway',
        glossary: 'glossary',
        'operator-card': 'operator',
      };
      const segment = typeMap[data.type] ?? data.type;
      router.push(`/${courseSlug}/${segment}/${data.slug}`);
    },
    [router, courseSlug]
  );

  return (
    <div style={{ width: '100%', height: '100%', background: '#0d0d0d' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        maxZoom={2}
        defaultEdgeOptions={{
          style: { stroke: 'rgba(247, 195, 93, 0.25)', strokeWidth: 1.5 },
          type: 'smoothstep',
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Controls
          style={{
            background: '#1a1a1a',
            border: '1px solid #333',
            borderRadius: 8,
          }}
        />
        <MiniMap
          nodeColor={(n) => {
            const data = n.data as CodexNodeData;
            return typeColors[data?.type] ?? '#555';
          }}
          maskColor="rgba(0,0,0,0.6)"
          style={{
            background: '#1a1a1a',
            border: '1px solid #333',
            borderRadius: 8,
          }}
        />
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="#222"
        />
      </ReactFlow>
    </div>
  );
}
