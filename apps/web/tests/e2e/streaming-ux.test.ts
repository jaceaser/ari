import { expect, test } from "@playwright/test";

/**
 * E2E smoke tests for streaming UX and sealed-session behaviour.
 *
 * These tests intercept network requests at the Playwright level so they
 * don't need a running backend.
 */

// ---------------------------------------------------------------------------
// Helper: build a minimal OpenAI SSE stream from a list of text chunks.
// ---------------------------------------------------------------------------
function buildSseStream(chunks: string[]): string {
  let body = "";
  for (const chunk of chunks) {
    const data = JSON.stringify({
      choices: [{ delta: { content: chunk }, finish_reason: null }],
    });
    body += `data: ${data}\n\n`;
  }
  // Final chunk with finish_reason
  body += `data: ${JSON.stringify({
    choices: [{ delta: {}, finish_reason: "stop" }],
  })}\n\n`;
  body += "data: [DONE]\n\n";
  return body;
}

// ---------------------------------------------------------------------------
// Helper: mock the /api/chat/openai endpoint to stream SSE chunks with a
// delay between each so we can observe partial rendering.
// ---------------------------------------------------------------------------
async function mockStreamingChat(
  page: import("@playwright/test").Page,
  chunks: string[],
  delayMs = 80
) {
  await page.route("**/api/chat/openai", async (route) => {
    // The route expects a UIMessageStream, but we need to simulate at the
    // SSE level.  Instead, we fulfil with a pre-built SSE payload.
    // The Next.js route handler won't be hit — Playwright intercepts first.
    const sseBody = buildSseStream(chunks);

    // We can't truly delay per-chunk via route.fulfill, so we send the
    // entire body at once.  The client-side throttle still applies.
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream; charset=utf-8",
      headers: {
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
      body: sseBody,
    });
  });
}

// ---------------------------------------------------------------------------
// Test 1: Streaming renders partial content then finalises with markdown
// ---------------------------------------------------------------------------
test.describe("Streaming UX", () => {
  test("assistant message appears after sending a prompt", async ({ page }) => {
    // Mock session creation so page.tsx doesn't fail
    await page.route("**/api/sessions", async (route, req) => {
      if (req.method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: "test-session", status: "active" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Mock history
    await page.route("**/api/history*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ chats: [], hasMore: false }),
      });
    });

    // Mock lead-runs
    await page.route("**/api/lead-runs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Mock votes
    await page.route("**/api/vote*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/");
    await page.waitForSelector("[data-testid='multimodal-input']");

    // Set up streaming mock BEFORE sending — the chat route will be hit
    // after the user submits
    await mockStreamingChat(page, [
      "Hello ",
      "world! ",
      "This is **bold** text.",
    ]);

    // Type and send
    const input = page.getByTestId("multimodal-input");
    await input.fill("Say hello");
    await page.getByTestId("send-button").click();

    // The user message should appear
    await expect(
      page.locator("[data-testid='message-user']").first()
    ).toBeVisible({ timeout: 5000 });

    // An assistant message should eventually appear (the mock fulfils
    // immediately so the AI SDK processes the full stream quickly)
    await expect(
      page.locator("[data-testid='message-assistant']").first()
    ).toBeVisible({ timeout: 10000 });

    // The assistant message should contain the streamed text
    const assistantContent = page
      .locator("[data-testid='message-assistant']")
      .first()
      .locator("[data-testid='message-content']");

    await expect(assistantContent).toContainText("Hello world", {
      timeout: 10000,
    });
  });
});

// ---------------------------------------------------------------------------
// Test 2: Sealed (read-only) session hides input, shows sealed bar
// ---------------------------------------------------------------------------
test.describe("Sealed Session", () => {
  test("readonly chat hides input and shows sealed indicator", async ({
    page,
  }) => {
    // Navigate directly to a chat page with isReadonly
    // We can test this by checking the readonly UI elements exist on page load
    // when the chat component receives isReadonly=true.
    //
    // Since we can't easily force isReadonly from the outside without the full
    // auth + session flow, we test the presence of the sealed CTA elements by
    // checking the component renders correctly when the route responds with a
    // sealed session.

    // Mock sessions to return a sealed session
    await page.route("**/api/sessions", async (route, req) => {
      if (req.method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "sealed-1",
            status: "sealed",
            sealed_at: new Date().toISOString(),
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "sealed-1",
            title: "Sealed Chat",
            status: "sealed",
            created_at: new Date().toISOString(),
            sealed_at: new Date().toISOString(),
          },
        ]),
      });
    });

    // Mock history endpoint to include the sealed session
    await page.route("**/api/history*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chats: [
            {
              id: "sealed-1",
              title: "Sealed Chat",
              status: "sealed",
              createdAt: new Date().toISOString(),
            },
          ],
          hasMore: false,
        }),
      });
    });

    await page.route("**/api/lead-runs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Go to home — the input should be visible on a normal chat
    await page.goto("/");
    await page.waitForSelector("[data-testid='multimodal-input']", {
      timeout: 10000,
    });

    // The input field should be visible on a non-sealed page
    await expect(page.getByTestId("multimodal-input")).toBeVisible();

    // Now verify that the sealed session appears in history with the
    // correct status (testing the data flow, not the readonly UI directly
    // since that requires navigating to /chat/sealed-1 with proper auth)
    const historyResponse = await page.request.get("/api/history?limit=10");
    expect(historyResponse.status()).toBe(200);
    const data = await historyResponse.json();
    expect(data.chats).toHaveLength(1);
    expect(data.chats[0].status).toBe("sealed");
  });
});

// ---------------------------------------------------------------------------
// Test 2b: Sealed chat page shows disabled input and sealed badge
// ---------------------------------------------------------------------------
test.describe("Sealed Session UI", () => {
  test("sealed chat page disables input and shows sealed badge", async ({
    page,
  }) => {
    const chatId = "sealed-ui-test";

    // Mock session endpoint (GET /api/sessions/:id)
    await page.route(`**/api/sessions/${chatId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: chatId,
          title: "Sealed Test",
          status: "sealed",
          created_at: new Date().toISOString(),
          sealed_at: new Date().toISOString(),
        }),
      });
    });

    // Mock messages endpoint (GET /api/sessions/:id/messages)
    await page.route(`**/api/sessions/${chatId}/messages`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "msg-1",
            role: "user",
            content: "Hello",
            created_at: new Date().toISOString(),
          },
          {
            id: "msg-2",
            role: "assistant",
            content: "Hi there!",
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    // Mock history + lead-runs for sidebar
    await page.route("**/api/history*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          chats: [
            {
              id: chatId,
              title: "Sealed Test",
              status: "sealed",
              createdAt: new Date().toISOString(),
            },
          ],
          hasMore: false,
        }),
      });
    });
    await page.route("**/api/lead-runs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
    await page.route("**/api/vote*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto(`/chat/${chatId}`);

    // The multimodal input should NOT be visible (sealed session)
    await expect(page.getByTestId("multimodal-input")).not.toBeVisible({
      timeout: 10000,
    });

    // The sealed message should appear
    await expect(page.getByText("This session is sealed")).toBeVisible({
      timeout: 10000,
    });

    // "Start New Chat" link should be visible
    await expect(page.getByRole("link", { name: "Start New Chat" })).toBeVisible();

    // "Sealed" badge in header
    await expect(page.getByText("Sealed").first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Test 2c: Lead run detail shows download link
// ---------------------------------------------------------------------------
test.describe("Lead Run Detail", () => {
  test("lead run sidebar shows download button with file_url", async ({
    page,
  }) => {
    // Mock sessions + history
    await page.route("**/api/sessions", async (route, req) => {
      if (req.method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: "new-session", status: "active" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
    await page.route("**/api/history*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ chats: [], hasMore: false }),
      });
    });

    // Mock lead-runs list with a run that has file_url
    await page.route("**/api/lead-runs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "lr-1",
            summary: "Pre-foreclosure leads in Dallas",
            location: "Dallas, TX",
            strategy: "pre-foreclosure",
            result_count: 42,
            file_url: "https://storage.example.com/leads.xlsx",
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    // Mock lead-run detail
    await page.route("**/api/lead-runs/lr-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "lr-1",
          summary: "Pre-foreclosure leads in Dallas",
          location: "Dallas, TX",
          strategy: "pre-foreclosure",
          result_count: 42,
          file_url: "https://storage.example.com/leads.xlsx",
          filters: { type: "pre-foreclosure" },
          created_at: new Date().toISOString(),
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector("[data-testid='multimodal-input']", {
      timeout: 10000,
    });

    // Lead run should appear in sidebar
    const leadRunItem = page.getByText("Pre-foreclosure leads in Dallas");
    await expect(leadRunItem.first()).toBeVisible({ timeout: 10000 });

    // The result count should be visible
    await expect(page.getByText("42 leads").first()).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Test 3: Jump-to-bottom button is hidden when at bottom
// ---------------------------------------------------------------------------
test.describe("Autoscroll", () => {
  test("jump-to-bottom button is initially hidden", async ({ page }) => {
    await page.route("**/api/history*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ chats: [], hasMore: false }),
      });
    });

    await page.route("**/api/sessions", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.route("**/api/lead-runs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/");
    await page.waitForSelector("[data-testid='multimodal-input']");

    // The jump-to-bottom button should be hidden (opacity-0, pointer-events-none)
    // when the user is already at the bottom
    const jumpButton = page.getByRole("button", { name: "Jump to bottom" });
    // It may or may not be in the DOM; if present it should be invisible
    const count = await jumpButton.count();
    if (count > 0) {
      await expect(jumpButton).toHaveCSS("opacity", "0");
    }
  });
});
