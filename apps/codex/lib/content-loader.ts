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
  AppendixSection,
} from '@/types/codex';
import type { Locale } from './translations';

const courseCache = new Map<string, Course>();

function convertMdTables(md: string): string {
  const lines = md.split('\n');
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    // Detect a table: line starts and ends with |, and the next line is a separator row
    const isSeparator = (l: string) => /^\|[\s|:-]+\|$/.test(l.trim());
    const isPipeLine = (l: string) => l.trim().startsWith('|') && l.trim().endsWith('|');

    if (isPipeLine(line) && i + 1 < lines.length && isSeparator(lines[i + 1])) {
      // Collect all table rows
      const tableLines: string[] = [];
      while (i < lines.length && isPipeLine(lines[i])) {
        tableLines.push(lines[i]);
        i++;
      }

      const parseRow = (l: string) =>
        l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());

      const headerCells = parseRow(tableLines[0]);
      // tableLines[1] is separator — skip it
      const bodyRows = tableLines.slice(2);

      const th = headerCells.map((c) => `<th>${c}</th>`).join('');
      const rows = bodyRows
        .map((row) => {
          const cells = parseRow(row);
          return `<tr>${cells.map((c) => `<td>${c}</td>`).join('')}</tr>`;
        })
        .join('\n');

      out.push(
        `<table>\n<thead><tr>${th}</tr></thead>\n<tbody>\n${rows}\n</tbody>\n</table>`
      );
    } else {
      out.push(line);
      i++;
    }
  }

  return out.join('\n');
}

async function markdownToHtml(content: string): Promise<string> {
  const withTables = convertMdTables(content);
  const result = await remark().use(remarkHtml, { sanitize: false }).process(withTables);
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

const US_STATES = new Set([
  'alabama','alaska','arizona','arkansas','california','colorado','connecticut',
  'delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa',
  'kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan',
  'minnesota','mississippi','missouri','montana','nebraska','nevada',
  'new-hampshire','new-jersey','new-mexico','new-york','north-carolina',
  'north-dakota','ohio','oklahoma','oregon','pennsylvania','rhode-island',
  'south-carolina','south-dakota','tennessee','texas','utah','vermont',
  'virginia','washington','west-virginia','wisconsin','wyoming',
  'district-of-columbia','american-samoa','guam','northern-mariana-islands',
  'puerto-rico','us-virgin-islands',
]);

function titleFromMarkdown(content: string, slug: string): string {
  const match = content.match(/^#+ (.+)/m);
  if (match) return match[1].replace(/\*/g, '').trim();
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

async function loadAppendix(dir: string): Promise<Map<string, AppendixSection>> {
  const map = new Map<string, AppendixSection>();
  if (!fs.existsSync(dir)) return map;

  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.md'));
  for (const file of files) {
    const slug = file.replace(/\.md$/, '');
    const raw = fs.readFileSync(path.join(dir, file), 'utf-8');
    const title = titleFromMarkdown(raw, slug);
    const category: AppendixSection['category'] = US_STATES.has(slug)
      ? 'state'
      : slug.startsWith('fifty-state') || slug.startsWith('i-') || slug.startsWith('ii-') || slug.startsWith('iii-') || slug.startsWith('iv-') || slug.startsWith('v-') || slug === 'states' || slug === 'list-form-written-out-state-by-state' || slug === 'us-territories'
      ? 'survey'
      : 'intro';
    const body = await markdownToHtml(raw);
    map.set(slug, { slug, title, category, body });
  }
  return map;
}

function getLocaleDir(baseDir: string, locale: Locale): string {
  if (locale === 'en') return baseDir;
  const localeDir = path.join(baseDir, locale);
  if (fs.existsSync(localeDir)) return localeDir;
  return baseDir;
}

export async function loadCourse(courseSlug: string, locale: Locale = 'en'): Promise<Course> {
  const cacheKey = `${courseSlug}:${locale}`;
  if (courseCache.has(cacheKey)) {
    return courseCache.get(cacheKey)!;
  }

  const base = path.join(process.cwd(), 'course-guides', courseSlug);

  // Load config — use locale-specific config if it exists
  const localeConfigPath = path.join(base, `course.config.${locale}.yaml`);
  const defaultConfigPath = path.join(base, 'course.config.yaml');
  const configPath = locale !== 'en' && fs.existsSync(localeConfigPath) ? localeConfigPath : defaultConfigPath;
  const configRaw = fs.readFileSync(configPath, 'utf-8');
  const config = yaml.load(configRaw) as CourseConfig;

  // Load overview
  const overviewRaw = fs.readFileSync(path.join(base, 'overview.md'), 'utf-8');
  const overview = await markdownToHtml(overviewRaw);

  // Load all entity types — check locale subdirectory first
  const topics = await loadEntitiesFromDir<Topic>(
    getLocaleDir(path.join(base, 'topics'), locale),
    'topic'
  );
  const caseStudies = await loadEntitiesFromDir<CaseStudy>(
    getLocaleDir(path.join(base, 'case-studies'), locale),
    'case-study'
  );
  const pathways = await loadEntitiesFromDir<Pathway>(
    getLocaleDir(path.join(base, 'pathways'), locale),
    'pathway'
  );
  const operatorCards = await loadEntitiesFromDir<OperatorCard>(
    getLocaleDir(path.join(base, 'operator-cards'), locale),
    'operator-card'
  );
  const glossary = await loadEntitiesFromDir<GlossaryTerm>(
    getLocaleDir(path.join(base, 'glossary'), locale),
    'glossary'
  );
  const appendix = await loadAppendix(path.join(base, 'extracted', 'appendix'));

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
    appendix,
    allEntities,
  };

  courseCache.set(cacheKey, course);
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
    appendix: Array.from(course.appendix.values()),
    allEntities: Object.fromEntries(course.allEntities),
  };
}
