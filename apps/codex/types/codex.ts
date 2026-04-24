export type EntityType = 'topic' | 'case-study' | 'operator-card' | 'glossary' | 'pathway' | 'document' | 'state-note';

export interface CodexEntity {
  id: string;
  slug: string;
  title: string;
  type: EntityType;
  summary: string;
  tags: string[];
  aliases: string[];
  relatedNodes: string[];
  prerequisites: string[];
  searchTerms: string[];
  order?: number;
  featured?: boolean;
  stateScope?: string[];
  body: string;
}

export interface Topic extends CodexEntity {
  type: 'topic';
  plainEnglish: string;
  whyItMatters: string;
  whenUsed: string;
  applicabilitySignals: string[];
  disqualifiers: string[];
  risks: string[];
  nextSteps: string[];
  operatorNotes: string;
  estimatedReadTime: number;
  difficultyLevel: 'beginner' | 'intermediate' | 'advanced';
}

export interface CaseStudy extends CodexEntity {
  type: 'case-study';
  scenario: string;
  doctrines: string[];
  play: string;
  outcome: string;
  takeaway: string;
}

export interface Pathway extends CodexEntity {
  type: 'pathway';
  entryCondition: string;
  steps: PathwayStep[];
  likelyDocuments: string[];
  stateSensitivity: string;
}

export interface PathwayStep {
  order: number;
  topicSlug: string;
  label: string;
  decisionPoints?: string[];
  risks?: string[];
}

export interface OperatorCard extends CodexEntity {
  type: 'operator-card';
  checklist: string[];
  commonMistakes: string[];
  scripts?: string[];
}

export interface GlossaryTerm extends CodexEntity {
  type: 'glossary';
  definition: string;
  relatedTerms: string[];
  plainEnglish?: string;
}

export interface CourseConfig {
  slug: string;
  title: string;
  description: string;
  productSlug: string;
  version: string;
  featured: {
    topics: string[];
    caseStudies: string[];
    pathways: string[];
  };
}

export interface Course {
  config: CourseConfig;
  overview: string;
  topics: Map<string, Topic>;
  caseStudies: Map<string, CaseStudy>;
  pathways: Map<string, Pathway>;
  operatorCards: Map<string, OperatorCard>;
  glossary: Map<string, GlossaryTerm>;
  allEntities: Map<string, CodexEntity>;
}

export interface SerializedCourse {
  config: CourseConfig;
  overview: string;
  topics: Topic[];
  caseStudies: CaseStudy[];
  pathways: Pathway[];
  operatorCards: OperatorCard[];
  glossary: GlossaryTerm[];
  allEntities: Record<string, CodexEntity>;
}
