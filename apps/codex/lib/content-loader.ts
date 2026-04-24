import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { remark } from 'remark';
import remarkHtml from 'remark-html';
import yaml from 'js-yaml';
import type {
  Course,
  SerializedCourse,
  CourseConfig,
  CodexEntity,
  Topic,
  CaseStudy,
  Pathway,
  OperatorCard,
  GlossaryTerm,
} from '@/types/codex';

const courseCache = new Map<string, Course>();

async function markdownToHtml(content: string): Promise<string> {
  const result = await remark().use(remarkHtml).process(content);
  return result.toString();
}

function parseEntity<T extends CodexEntity>(
  filePath: string,
  overrideType?: string
): T | null {
  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    const { data, content } = matter(raw);
    return {
      ...data,
      type: overrideType ?? data.type,
      body: content,
      tags: data.tags ?? [],
      aliases: data.aliases ?? [],
      relatedNodes: data.relatedNodes ?? [],
      prerequisites: data.prerequisites ?? [],
      searchTerms: data.searchTerms ?? [],
    } as T;
  } catch {
    return null;
  }
}

async function loadEntitiesFromDir<T extends CodexEntity>(
  dir: string,
  type: string
): Promise<Map<string, T>> {
  const map = new Map<string, T>();
  if (!fs.existsSync(dir)) return map;

  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.md'));
  for (const file of files) {
    const entity = parseEntity<T>(path.join(dir, file), type);
    if (entity) {
      entity.body = await markdownToHtml(entity.body);
      map.set(entity.slug, entity);
    }
  }
  return map;
}

export async function loadCourse(courseSlug: string): Promise<Course> {
  if (courseCache.has(courseSlug)) {
    return courseCache.get(courseSlug)!;
  }

  const base = path.join(process.cwd(), 'course-guides', courseSlug);

  // Load config
  const configRaw = fs.readFileSync(path.join(base, 'course.config.yaml'), 'utf-8');
  const config = yaml.load(configRaw) as CourseConfig;

  // Load overview
  const overviewRaw = fs.readFileSync(path.join(base, 'overview.md'), 'utf-8');
  const overview = await markdownToHtml(overviewRaw);

  // Load all entity types
  const topics = await loadEntitiesFromDir<Topic>(path.join(base, 'topics'), 'topic');
  const caseStudies = await loadEntitiesFromDir<CaseStudy>(
    path.join(base, 'case-studies'),
    'case-study'
  );
  const pathways = await loadEntitiesFromDir<Pathway>(
    path.join(base, 'pathways'),
    'pathway'
  );
  const operatorCards = await loadEntitiesFromDir<OperatorCard>(
    path.join(base, 'operator-cards'),
    'operator-card'
  );
  const glossary = await loadEntitiesFromDir<GlossaryTerm>(
    path.join(base, 'glossary'),
    'glossary'
  );

  // Build allEntities map
  const allEntities = new Map<string, CodexEntity>();
  for (const [k, v] of topics) allEntities.set(k, v);
  for (const [k, v] of caseStudies) allEntities.set(k, v);
  for (const [k, v] of pathways) allEntities.set(k, v);
  for (const [k, v] of operatorCards) allEntities.set(k, v);
  for (const [k, v] of glossary) allEntities.set(k, v);

  const course: Course = {
    config,
    overview,
    topics,
    caseStudies,
    pathways,
    operatorCards,
    glossary,
    allEntities,
  };

  courseCache.set(courseSlug, course);
  return course;
}

export function serializeCourse(course: Course): SerializedCourse {
  return {
    config: course.config,
    overview: course.overview,
    topics: Array.from(course.topics.values()),
    caseStudies: Array.from(course.caseStudies.values()),
    pathways: Array.from(course.pathways.values()),
    operatorCards: Array.from(course.operatorCards.values()),
    glossary: Array.from(course.glossary.values()),
    allEntities: Object.fromEntries(course.allEntities),
  };
}
