import type {
  LanguageModelV3GenerateResult,
  LanguageModelV3StreamPart,
} from "@ai-sdk/provider";
import { simulateReadableStream } from "ai";
import { MockLanguageModelV3 } from "ai/test";
import { getResponseChunksByPrompt } from "@/tests/prompts/utils";

const mockUsage = {
  inputTokens: { total: 10, noCache: 10, cacheRead: 0, cacheWrite: 0 },
  outputTokens: { total: 20, text: 20, reasoning: 0 },
};

const stopReason = { unified: "stop" as const, raw: "stop" };

const generateResult: LanguageModelV3GenerateResult = {
  finishReason: stopReason,
  usage: mockUsage,
  content: [{ type: "text", text: "Hello, world!" }],
  warnings: [],
};

const titleGenerateResult: LanguageModelV3GenerateResult = {
  finishReason: stopReason,
  usage: mockUsage,
  content: [{ type: "text", text: "This is a test title" }],
  warnings: [],
};

export const chatModel = new MockLanguageModelV3({
  doGenerate: generateResult,
  doStream: async ({ prompt }) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 500,
      initialDelayInMs: 1000,
      chunks: getResponseChunksByPrompt(prompt),
    }),
  }),
});

export const reasoningModel = new MockLanguageModelV3({
  doGenerate: generateResult,
  doStream: async ({ prompt }) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 500,
      initialDelayInMs: 1000,
      chunks: getResponseChunksByPrompt(prompt, true),
    }),
  }),
});

const titleStreamChunks: LanguageModelV3StreamPart[] = [
  { id: "1", type: "text-start" },
  { id: "1", type: "text-delta", delta: "This is a test title" },
  { id: "1", type: "text-end" },
  { type: "finish", finishReason: stopReason, usage: mockUsage },
];

export const titleModel = new MockLanguageModelV3({
  doGenerate: titleGenerateResult,
  doStream: async (_options) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 500,
      initialDelayInMs: 1000,
      chunks: titleStreamChunks,
    }),
  }),
});

export const artifactModel = new MockLanguageModelV3({
  doGenerate: generateResult,
  doStream: async ({ prompt }) => ({
    stream: simulateReadableStream({
      chunkDelayInMs: 50,
      initialDelayInMs: 100,
      chunks: getResponseChunksByPrompt(prompt),
    }),
  }),
});
