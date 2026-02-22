/**
 * Unit tests for ThrottledDeltaWriter from lib/sse-parser.ts.
 *
 * Run: npx tsx tests/unit/throttled-delta-writer.test.ts
 *
 * Verifies:
 * 1. Text is buffered (not written immediately)
 * 2. Buffered text is flushed at the configured interval
 * 3. finalize() flushes remaining text and stops the timer
 * 4. Multiple pushes between flushes are batched into one write
 */

import { ThrottledDeltaWriter, FLUSH_INTERVAL_MS } from "../../lib/sse-parser";

let passed = 0;
let failed = 0;

function assert(condition: boolean, name: string) {
  if (condition) {
    passed++;
    console.log(`  PASS: ${name}`);
  } else {
    failed++;
    console.error(`  FAIL: ${name}`);
  }
}

function createMockWriter() {
  const writes: any[] = [];
  return {
    write: (part: any) => writes.push(part),
    writes,
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runTests() {
  console.log("ThrottledDeltaWriter tests\n");

  // Test 1: FLUSH_INTERVAL_MS is exported and reasonable
  assert(
    typeof FLUSH_INTERVAL_MS === "number" && FLUSH_INTERVAL_MS > 0 && FLUSH_INTERVAL_MS <= 100,
    `FLUSH_INTERVAL_MS is ${FLUSH_INTERVAL_MS}ms (reasonable range)`
  );

  // Test 2: push() does not write immediately
  {
    const mock = createMockWriter();
    const w = new ThrottledDeltaWriter(mock, "t1");
    w.push("Hello");
    assert(mock.writes.length === 0, "push() does not write immediately");
    w.finalize();
  }

  // Test 3: finalize() flushes remaining text
  {
    const mock = createMockWriter();
    const w = new ThrottledDeltaWriter(mock, "t2");
    w.push("remaining");
    w.finalize();
    assert(mock.writes.length === 1, "finalize() produces exactly one write");
    assert(mock.writes[0]?.delta === "remaining", "finalize() flushes buffered text");
    assert(mock.writes[0]?.type === "text-delta", "write type is text-delta");
    assert(mock.writes[0]?.id === "t2", "write id matches");
  }

  // Test 4: Multiple pushes are batched
  {
    const mock = createMockWriter();
    const w = new ThrottledDeltaWriter(mock, "t3");
    w.push("A");
    w.push("B");
    w.push("C");
    w.finalize();
    assert(mock.writes.length === 1, "multiple pushes batched into one write");
    assert(mock.writes[0]?.delta === "ABC", "batched delta is concatenated");
  }

  // Test 5: Timer flush works within interval
  {
    const mock = createMockWriter();
    const w = new ThrottledDeltaWriter(mock, "t4");
    w.push("timer-test");
    await sleep(FLUSH_INTERVAL_MS + 20); // Wait slightly longer than interval
    assert(mock.writes.length >= 1, "timer flushes after interval");
    assert(mock.writes[0]?.delta === "timer-test", "timer-flushed text is correct");
    w.finalize();
  }

  // Test 6: finalize() on empty buffer does not write
  {
    const mock = createMockWriter();
    const w = new ThrottledDeltaWriter(mock, "t5");
    w.finalize();
    assert(mock.writes.length === 0, "finalize() on empty buffer writes nothing");
  }

  // Test 7: Two flush intervals produce two writes
  {
    const mock = createMockWriter();
    const w = new ThrottledDeltaWriter(mock, "t6");
    w.push("batch1");
    await sleep(FLUSH_INTERVAL_MS + 20);
    w.push("batch2");
    await sleep(FLUSH_INTERVAL_MS + 20);
    const beforeFinalize = mock.writes.length;
    w.finalize();
    assert(beforeFinalize >= 2, `two intervals produce ${beforeFinalize} writes (expected >= 2)`);
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

runTests();
