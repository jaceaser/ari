import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import type { CourseConfig } from '@/types/codex';
import type { Locale } from '@/lib/translations';

export interface CourseSummary {
  config: CourseConfig;
  slug: string;
  topicCount: number;
  caseStudyCount: number;
  pathwayCount: number;
}

function countFiles(dir: string): number {
  if (!fs.existsSync(dir)) return 0;
  return fs.readdirSync(dir).filter((f) => f.endsWith('.md')).length;
}

function loadConfig(courseDir: string, locale: Locale): CourseConfig | null {
  // Try locale-specific config first, fall back to default
  const candidates =
    locale === 'en'
      ? ['course.config.yaml']
      : [`course.config.${locale}.yaml`, 'course.config.yaml'];

  for (const name of candidates) {
    const p = path.join(courseDir, name);
    if (fs.existsSync(p)) {
      try {
        return yaml.load(fs.readFileSync(p, 'utf-8')) as CourseConfig;
      } catch {
        continue;
      }
    }
  }
  return null;
}

export function listCourses(locale: Locale = 'en'): CourseSummary[] {
  const base = path.join(process.cwd(), 'course-guides');
  if (!fs.existsSync(base)) return [];

  const slugs = fs
    .readdirSync(base, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  const courses: CourseSummary[] = [];

  for (const slug of slugs) {
    const courseDir = path.join(base, slug);
    const config = loadConfig(courseDir, locale);
    if (!config) continue;

    courses.push({
      config,
      slug,
      topicCount: countFiles(path.join(courseDir, 'topics')),
      caseStudyCount: countFiles(path.join(courseDir, 'case-studies')),
      pathwayCount: countFiles(path.join(courseDir, 'pathways')),
    });
  }

  return courses;
}
