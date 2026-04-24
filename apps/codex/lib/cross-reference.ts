import type { SerializedCourse, CodexEntity, EntityType, Pathway, Topic } from '@/types/codex';

export interface CrossRef {
  sourceSlug: string;
  sourceTitle: string;
  sourceType: EntityType;
  chapterTitle: string;
  context: string;
}

export type CrossReferenceIndex = Record<string, CrossRef[]>;

function getChapterTitle(entity: CodexEntity): string {
  switch (entity.type) {
    case 'topic': return 'Part I — The Strategy';
    case 'case-study': return 'Part II — Case Studies';
    case 'pathway': return 'Part III — Pathways';
    case 'operator-card': return 'Operator Reference';
    case 'glossary': return 'Glossary';
    default: return 'Course Content';
  }
}

export function buildCrossReferenceIndex(course: SerializedCourse): CrossReferenceIndex {
  const index: CrossReferenceIndex = {};

  function addRef(targetSlug: string, source: CodexEntity, context: string) {
    if (!targetSlug || targetSlug === source.slug) return;
    if (!index[targetSlug]) index[targetSlug] = [];
    const exists = index[targetSlug].some(
      (r) => r.sourceSlug === source.slug && r.context === context
    );
    if (!exists) {
      index[targetSlug].push({
        sourceSlug: source.slug,
        sourceTitle: source.title,
        sourceType: source.type,
        chapterTitle: getChapterTitle(source),
        context,
      });
    }
  }

  const allEntities = Object.values(course.allEntities);

  for (const entity of allEntities) {
    for (const slug of entity.relatedNodes ?? []) {
      addRef(slug, entity, `Related in "${entity.title}"`);
    }
    for (const slug of (entity as Topic).prerequisites ?? []) {
      addRef(slug, entity, `Prerequisite for "${entity.title}"`);
    }
    for (const slug of (entity as Topic).nextSteps ?? []) {
      addRef(slug, entity, `Next step in "${entity.title}"`);
    }
  }

  for (const cs of course.caseStudies) {
    for (const slug of cs.doctrines ?? []) {
      addRef(slug, cs, `Doctrine used in case study`);
    }
  }

  for (const pw of course.pathways) {
    for (const step of (pw as Pathway).steps ?? []) {
      if (step.topicSlug) {
        addRef(step.topicSlug, pw, `Step ${step.order}: "${step.label}"`);
      }
    }
  }

  return index;
}
