import Fuse from 'fuse.js';
import type { Course, CodexEntity, Topic, GlossaryTerm } from '@/types/codex';

export function searchCourse(course: Course, query: string): CodexEntity[] {
  if (!query.trim()) return [];

  const entities = Array.from(course.allEntities.values());

  const fuse = new Fuse(entities, {
    keys: [
      { name: 'title', weight: 2 },
      { name: 'summary', weight: 1.5 },
      { name: 'aliases', weight: 1.5 },
      { name: 'searchTerms', weight: 1.5 },
      { name: 'tags', weight: 1 },
      { name: 'plainEnglish', weight: 1 },
      { name: 'definition', weight: 1 },
    ],
    threshold: 0.4,
    includeScore: true,
  });

  return fuse.search(query).map((r) => r.item);
}

export interface SearchableEntity {
  id: string;
  slug: string;
  title: string;
  type: string;
  summary: string;
  aliases: string[];
  searchTerms: string[];
  tags: string[];
  plainEnglish?: string;
  definition?: string;
}

export function buildSearchData(course: Course): SearchableEntity[] {
  return Array.from(course.allEntities.values()).map((e) => ({
    id: e.id,
    slug: e.slug,
    title: e.title,
    type: e.type,
    summary: e.summary,
    aliases: e.aliases ?? [],
    searchTerms: e.searchTerms ?? [],
    tags: e.tags ?? [],
    plainEnglish: (e as Topic).plainEnglish,
    definition: (e as GlossaryTerm).definition,
  }));
}
