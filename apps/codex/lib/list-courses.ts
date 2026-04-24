import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import type { CourseConfig } from '@/types/codex';

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

export function listCourses(): CourseSummary[] {
  const base = path.join(process.cwd(), 'course-guides');
  if (!fs.existsSync(base)) return [];

  const slugs = fs
    .readdirSync(base, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);

  const courses: CourseSummary[] = [];

  for (const slug of slugs) {
    const courseDir = path.join(base, slug);
    const configPath = path.join(courseDir, 'course.config.yaml');
    if (!fs.existsSync(configPath)) continue;

    try {
      const raw = fs.readFileSync(configPath, 'utf-8');
      const config = yaml.load(raw) as CourseConfig;

      courses.push({
        config,
        slug,
        topicCount: countFiles(path.join(courseDir, 'topics')),
        caseStudyCount: countFiles(path.join(courseDir, 'case-studies')),
        pathwayCount: countFiles(path.join(courseDir, 'pathways')),
      });
    } catch {
      // skip malformed course
    }
  }

  return courses;
}
