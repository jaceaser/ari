"use client";

import type { UseChatHelpers } from "@ai-sdk/react";
import { motion } from "framer-motion";
import { memo, useMemo } from "react";
import type { ChatMessage } from "@/lib/types";
import { Suggestion } from "./elements/suggestion";
import type { VisibilityType } from "./visibility-selector";

// ── Curated real-estate prompts by category ──

const promptsByCategory: Record<string, string[]> = {
  Leads: [
    "Get tired landlords in Harris County, TX.",
    "Pull pre-foreclosures in Bexar County, TX.",
    "Find FSBO listings in Dallas County, TX.",
    "Show me fixer-uppers in Tarrant County, TX.",
    "Get as-is listings in Travis County, TX.",
    "Find subject-to leads in Maricopa County, AZ.",
    "Pull pre-foreclosures in Clark County, NV.",
    "Get land listings in Williamson County, TX.",
  ],
  Buyers: [
    "Find cash buyers for 78245 in San Antonio.",
    "Show me active cash buyers in Houston, TX.",
    "Find buyers for wholesale deals in Dallas, TX.",
    "Pull cash buyer leads in Atlanta, GA.",
  ],
  Comps: [
    "Estimate ARV using comps within 0.5 miles for [address].",
    "Run comps on a 3/2 1,400 sqft home in 77084.",
    "How do I run comps in a non-disclosure state like Texas?",
    "What PPSF adjustments should I make for a missing garage?",
  ],
  Contracts: [
    "Draft a simple wholesale assignment addendum for Texas.",
    "Create a subject-to purchase agreement for a property in Florida.",
    "Draft a lease option agreement for a single-family home.",
    "Write a novation agreement template for Texas.",
  ],
  Strategy: [
    "What is a novation and when should I use it?",
    "Walk me through the BRRRR strategy step by step.",
    "How do I structure a subject-to deal with seller financing?",
    "Compare wholesaling vs novation for a motivated seller.",
    "What's the best exit strategy for a property with 30% equity?",
    "How do I calculate MAO for a flip in a hot market?",
    "Explain creative finance options for a seller with low equity.",
    "What due diligence should I run before a wholesale deal?",
  ],
};

/** Pick N random items from an array without repeats. */
function pickRandom<T>(arr: T[], n: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
}

/** Select 4 prompts: one from each of 4 randomly-chosen categories. */
function selectPrompts(): string[] {
  const categories = Object.keys(promptsByCategory);
  const chosen = pickRandom(categories, 4);
  return chosen.map(
    (cat) => pickRandom(promptsByCategory[cat], 1)[0]
  );
}

type SuggestedActionsProps = {
  chatId: string;
  sendMessage: UseChatHelpers<ChatMessage>["sendMessage"];
  selectedVisibilityType: VisibilityType;
};

function PureSuggestedActions({ chatId, sendMessage }: SuggestedActionsProps) {
  // useMemo with empty deps = stable per mount (new chat page = new mount = new shuffle)
  const suggestedActions = useMemo(() => selectPrompts(), []);

  return (
    <div
      className="grid w-full gap-2 sm:grid-cols-2"
      data-testid="suggested-actions"
    >
      {suggestedActions.map((suggestedAction, index) => (
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          initial={{ opacity: 0, y: 20 }}
          key={suggestedAction}
          transition={{ delay: 0.05 * index }}
        >
          <Suggestion
            className="h-auto w-full whitespace-normal p-3 text-left"
            onClick={(suggestion) => {
              window.history.pushState({}, "", `/chat/${chatId}`);
              sendMessage({
                role: "user",
                parts: [{ type: "text", text: suggestion }],
              });
            }}
            suggestion={suggestedAction}
          >
            {suggestedAction}
          </Suggestion>
        </motion.div>
      ))}
    </div>
  );
}

export const SuggestedActions = memo(
  PureSuggestedActions,
  (prevProps, nextProps) => {
    if (prevProps.chatId !== nextProps.chatId) {
      return false;
    }
    if (prevProps.selectedVisibilityType !== nextProps.selectedVisibilityType) {
      return false;
    }

    return true;
  }
);
