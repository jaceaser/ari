'use client';
import { createContext, useContext } from 'react';
import type { Slide } from '@/lib/slide-builder';
import type { SerializedCourse } from '@/types/codex';
import type { CrossReferenceIndex } from '@/lib/cross-reference';

interface PresentationContextValue {
  course: SerializedCourse;
  courseSlug: string;
  slides: Slide[];
  currentIndex: number;
  navigateToSlug: (slug: string) => void;
  navigateToIndex: (index: number) => void;
  historyStack: number[];
  goBack: () => void;
  crossRefIndex: CrossReferenceIndex;
  explorerOpen: boolean;
  setExplorerOpen: (open: boolean) => void;
}

export const PresentationContext = createContext<PresentationContextValue | null>(null);

export function usePresentation() {
  const ctx = useContext(PresentationContext);
  if (!ctx) throw new Error('usePresentation must be used within PresentationContext');
  return ctx;
}
