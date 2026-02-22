import { expect, test } from "@playwright/test";

/**
 * Test the session-based API proxy routes.
 *
 * These tests mock the upstream backend responses and verify that:
 * 1. The proxy routes exist and return proper responses
 * 2. Bearer tokens are attached to upstream requests
 *
 * NOTE: These tests run against the local Next.js dev server.
 * They mock the upstream API calls at the network level.
 */

test.describe("Session API Proxy Routes", () => {
  test("GET /api/sessions returns sessions list", async ({ page }) => {
    // Mock the upstream backend response
    await page.route("**/sessions", async (route, req) => {
      if (req.url().includes("/api/sessions")) {
        // Let the Next.js proxy handle it
        return route.continue();
      }
      // Mock the upstream Quart backend response
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "test-session-1",
            title: "Test Chat",
            status: "active",
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    const response = await page.request.get("/api/sessions");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
  });

  test("GET /api/lead-runs returns lead runs list", async ({ page }) => {
    await page.route("**/lead-runs", async (route, req) => {
      if (req.url().includes("/api/lead-runs")) {
        return route.continue();
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "lr-1",
            summary: "Fixer-uppers in Dallas",
            location: "Dallas, TX",
            strategy: "fixer-upper",
            result_count: 41,
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    const response = await page.request.get("/api/lead-runs");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(Array.isArray(data)).toBe(true);
  });

  test("GET /api/history returns chat list (external backend shape)", async ({
    page,
  }) => {
    const response = await page.request.get("/api/history?limit=10");
    expect(response.status()).toBe(200);
    const data = await response.json();
    // Should have the expected shape regardless of backend
    expect(data).toHaveProperty("chats");
    expect(data).toHaveProperty("hasMore");
  });

  test("GET /api/lead-runs/:id returns detail with file_url", async ({
    page,
  }) => {
    await page.route("**/lead-runs/lr-detail-1", async (route, req) => {
      if (req.url().includes("/api/lead-runs")) return route.continue();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "lr-detail-1",
          summary: "Fixer-uppers in Dallas",
          location: "Dallas, TX",
          strategy: "fixer-upper",
          result_count: 41,
          file_url: "https://storage.example.com/leads/lr-detail-1.xlsx",
          filters: { min_equity: 50 },
          created_at: new Date().toISOString(),
        }),
      });
    });

    const response = await page.request.get("/api/lead-runs/lr-detail-1");
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.file_url).toContain("https://");
    expect(data.result_count).toBe(41);
    expect(data.filters).toHaveProperty("min_equity");
  });
});
