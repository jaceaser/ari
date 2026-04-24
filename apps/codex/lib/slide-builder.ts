import type { SerializedCourse } from '@/types/codex';

export type SlideType = 'hero' | 'chapter-intro' | 'topic' | 'case-study' | 'pathway' | 'glossary' | 'map';

export interface Slide {
  id: string;
  type: SlideType;
  chapterIndex: number;
  chapterTitle: string;
  shortTitle: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}

export function buildSlides(course: SerializedCourse): Slide[] {
  const slides: Slide[] = [];

  // 1. Hero
  slides.push({
    id: 'hero',
    type: 'hero',
    chapterIndex: 0,
    chapterTitle: 'Introduction',
    shortTitle: 'Welcome',
    data: { course },
  });

  // 2. Part I: The Strategy (topics)
  const sortedTopics = [...course.topics].sort((a, b) => (a.order ?? 99) - (b.order ?? 99));

  slides.push({
    id: 'chapter-strategy',
    type: 'chapter-intro',
    chapterIndex: 1,
    chapterTitle: 'The Strategy',
    shortTitle: 'Part I',
    data: {
      partNumber: 'PART I',
      title: 'THE STRATEGY',
      description:
        'What fractured equity is, why the opportunity exists, and how the acquisition model works.',
      slideCount: sortedTopics.length,
      items: sortedTopics.map((t) => t.title),
    },
  });

  sortedTopics.forEach((topic, i) => {
    slides.push({
      id: `topic-${topic.slug}`,
      type: 'topic',
      chapterIndex: 1,
      chapterTitle: 'The Strategy',
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
      chapterTitle: 'Case Studies',
      shortTitle: 'Part II',
      data: {
        partNumber: 'PART II',
        title: 'CASE STUDIES',
        description: 'Real deals. Real numbers. See how the strategy plays out in practice.',
        slideCount: course.caseStudies.length,
        items: course.caseStudies.map((cs) => cs.title),
      },
    });

    course.caseStudies.forEach((cs) => {
      slides.push({
        id: `cs-${cs.slug}`,
        type: 'case-study',
        chapterIndex: 2,
        chapterTitle: 'Case Studies',
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
      chapterTitle: 'Pathways',
      shortTitle: 'Part III',
      data: {
        partNumber: 'PART III',
        title: 'PATHWAYS',
        description: 'Guided routes through the most common operator scenarios.',
        slideCount: course.pathways.length,
        items: course.pathways.map((pw) => pw.title),
      },
    });

    course.pathways.forEach((pw) => {
      slides.push({
        id: `pathway-${pw.slug}`,
        type: 'pathway',
        chapterIndex: 3,
        chapterTitle: 'Pathways',
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
      chapterTitle: 'Glossary',
      shortTitle: 'Glossary',
      data: { terms: course.glossary },
    });
  }

  // 6. Knowledge Map
  slides.push({
    id: 'map',
    type: 'map',
    chapterIndex: 5,
    chapterTitle: 'Knowledge Map',
    shortTitle: 'Knowledge Map',
    data: {},
  });

  return slides;
}
