import { NextRequest, NextResponse } from 'next/server';
import { AzureOpenAI } from 'openai';
import { loadCourse } from '@/lib/content-loader';
import Fuse from 'fuse.js';
import type { CodexEntity } from '@/types/codex';

const openai = new AzureOpenAI({
  apiKey: process.env.AZURE_OPENAI_KEY,
  endpoint: process.env.AZURE_OPENAI_ENDPOINT,
  apiVersion: process.env.AZURE_OPENAI_API_VERSION ?? '2024-12-01-preview',
});

function buildEntityContext(entity: CodexEntity): string {
  const lines = [
    `### ${entity.title}`,
    `Link format: [[${entity.slug}|${entity.title}]]`,
    `Summary: ${entity.summary}`,
  ];
  const e = entity as unknown as Record<string, unknown>;
  if (e.plainEnglish) lines.push(`Plain English: ${e.plainEnglish}`);
  if (e.whyItMatters) lines.push(`Why It Matters: ${e.whyItMatters}`);
  if (e.whenUsed) lines.push(`When Used: ${e.whenUsed}`);
  if (Array.isArray(e.risks) && e.risks.length) {
    lines.push(`Risks: ${(e.risks as string[]).slice(0, 3).join('; ')}`);
  }
  if (e.operatorNotes) {
    lines.push(`Operator Notes: ${String(e.operatorNotes).slice(0, 400)}`);
  }
  if (e.scenario) lines.push(`Scenario: ${e.scenario}`);
  if (e.play) lines.push(`Play: ${e.play}`);
  if (e.outcome) lines.push(`Outcome: ${e.outcome}`);
  if (e.takeaway) lines.push(`Takeaway: ${e.takeaway}`);
  if (e.definition) lines.push(`Definition: ${e.definition}`);
  if (e.entryCondition) lines.push(`Entry Condition: ${e.entryCondition}`);
  return lines.join('\n');
}

export async function POST(req: NextRequest) {
  try {
    const { message, courseSlug, history = [] } = await req.json();

    if (!message || !courseSlug) {
      return NextResponse.json({ error: 'message and courseSlug required' }, { status: 400 });
    }

    const course = await loadCourse(courseSlug);
    const entities = Array.from(course.allEntities.values());

    const fuse = new Fuse(entities, {
      keys: [
        { name: 'title', weight: 2 },
        { name: 'summary', weight: 1.5 },
        { name: 'aliases', weight: 1.5 },
        { name: 'searchTerms', weight: 1.5 },
        { name: 'tags', weight: 1 },
      ],
      threshold: 0.5,
      includeScore: true,
    });

    // Build a context-aware search query: current message + recent conversation
    // so that follow-up questions like "where can I learn it?" resolve correctly
    const recentText = (history as { role: string; content: string }[])
      .slice(-4)
      .map((h) => h.content)
      .join(' ');
    const searchQuery = `${message} ${recentText}`.slice(0, 600).trim();

    const results = fuse.search(searchQuery);
    const topEntities = results.slice(0, 8).map((r) => r.item);
    // Fall back to a broader search on just the message if context query missed
    const fallback = topEntities.length === 0 ? fuse.search(message).slice(0, 6).map((r) => r.item) : [];
    const contextEntities = topEntities.length > 0 ? topEntities : fallback.length > 0 ? fallback : entities.slice(0, 6);

    const contextText = contextEntities.map(buildEntityContext).join('\n\n---\n\n');

    const systemPrompt = `You are ARI, an assistant for the "${course.config.title}" — a specialized real estate investment field manual.

STRICT RULES:
1. Answer ONLY from the course content provided below. Do not draw on outside knowledge.
2. If the answer is not found in the provided content, say: "I don't have information on that in this codex. Try the Content Explorer (press E) to browse all sections."
3. When referencing a section, use this exact format: [[slug|Display Title]] — these become clickable links. Example: [[chapter-05-intestate-succession|Intestate Succession]].
4. Use plain paragraphs. No markdown headers or bullet syntax. Keep answers concise and practical.
5. You may cite multiple sections if relevant.

COURSE CONTENT:
${contextText}`;

    const messages: { role: 'user' | 'assistant'; content: string }[] = [
      ...history.map((h: { role: string; content: string }) => ({
        role: h.role as 'user' | 'assistant',
        content: h.content,
      })),
      { role: 'user', content: message },
    ];

    const stream = await openai.chat.completions.create({
      model: 'gpt-5-mini',
      max_completion_tokens: 1024,
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages.map((m) => ({ role: m.role, content: m.content })),
      ],
      stream: true,
    });

    const encoder = new TextEncoder();
    const readable = new ReadableStream({
      async start(controller) {
        for await (const chunk of stream) {
          const text = chunk.choices[0]?.delta?.content;
          if (text) controller.enqueue(encoder.encode(text));
        }
        controller.close();
      },
    });

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal error';
    console.error('[ARI chat]', error);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
