import type { SerializedCourse } from '@/types/codex';
import type { Translations } from './translations';
import { translations } from './translations';

export type SlideType = 'hero' | 'chapter-intro' | 'topic' | 'case-study' | 'pathway' | 'glossary' | 'map' | 'appendix';

export interface Slide {
  id: string;
  type: SlideType;
  chapterIndex: number;
  chapterTitle: string;
  shortTitle: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}

export function buildSlides(course: SerializedCourse, t: Translations = translations.en): Slide[] {
  const slides: Slide[] = [];

  // 1. Hero
  slides.push({
    id: 'hero',
    type: 'hero',
    chapterIndex: 0,
    chapterTitle: t.introduction,
    shortTitle: t.welcome,
    data: { course },
  });

  // 2. Part I: The Strategy (topics)
  const sortedTopics = [...course.topics].sort((a, b) => (a.order ?? 99) - (b.order ?? 99));

  slides.push({
    id: 'chapter-strategy',
    type: 'chapter-intro',
    chapterIndex: 1,
    chapterTitle: t.theStrategy,
    shortTitle: t.partI,
    data: {
      partNumber: t.partI,
      title: t.theStrategy,
      description: t.strategyDescription,
      slideCount: sortedTopics.length,
      items: sortedTopics.map((tp) => tp.title),
    },
  });

  sortedTopics.forEach((topic, i) => {
    slides.push({
      id: `topic-${topic.slug}`,
      type: 'topic',
      chapterIndex: 1,
      chapterTitle: t.theStrategy,
      shortTitle: topic.title,
      data: {
        topic,
        slideNumber: i + 1,
        totalTopics: sortedTopics.length,
      },
    });
  });

  // 3. Part II: Case Studies
  if (course.caseStudies.length > 0) {
    slides.push({
      id: 'chapter-casestudies',
      type: 'chapter-intro',
      chapterIndex: 2,
      chapterTitle: t.caseStudies,
      shortTitle: t.partII,
      data: {
        partNumber: t.partII,
        title: t.caseStudies,
        description: t.caseStudiesDescription,
        slideCount: course.caseStudies.length,
        items: course.caseStudies.map((cs) => cs.title),
      },
    });

    course.caseStudies.forEach((cs) => {
      slides.push({
        id: `cs-${cs.slug}`,
        type: 'case-study',
        chapterIndex: 2,
        chapterTitle: t.caseStudies,
        shortTitle: cs.title,
        data: { caseStudy: cs },
      });
    });
  }

  // 4. Part III: Pathways
  if (course.pathways.length > 0) {
    slides.push({
      id: 'chapter-pathways',
      type: 'chapter-intro',
      chapterIndex: 3,
      chapterTitle: t.pathways,
      shortTitle: t.partIII,
      data: {
        partNumber: t.partIII,
        title: t.pathways,
        description: t.pathwaysDescription,
        slideCount: course.pathways.length,
        items: course.pathways.map((pw) => pw.title),
      },
    });

    course.pathways.forEach((pw) => {
      slides.push({
        id: `pathway-${pw.slug}`,
        type: 'pathway',
        chapterIndex: 3,
        chapterTitle: t.pathways,
        shortTitle: pw.title,
        data: { pathway: pw },
      });
    });
  }

  // 5. Glossary
  if (course.glossary.length > 0) {
    slides.push({
      id: 'glossary',
      type: 'glossary',
      chapterIndex: 4,
      chapterTitle: t.glossary,
      shortTitle: t.glossary,
      data: { terms: course.glossary },
    });
  }

  // 6. Appendix
  if (course.appendix.length > 0) {
    slides.push({
      id: 'appendix',
      type: 'appendix',
      chapterIndex: 5,
      chapterTitle: t.appendix,
      shortTitle: t.appendix,
      data: { sectionCount: course.appendix.length },
    });
  }

  // 7. Knowledge Map
  slides.push({
    id: 'map',
    type: 'map',
    chapterIndex: 6,
    chapterTitle: t.knowledgeMap,
    shortTitle: t.knowledgeMap,
    data: {},
  });

  return slides;
}
