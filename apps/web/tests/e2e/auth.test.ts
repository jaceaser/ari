import { expect, test } from "@playwright/test";

test.describe("Authentication Pages", () => {
  test("login page renders email-only form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByPlaceholder("user@acme.com")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Send sign-in link" })
    ).toBeVisible();
    await expect(page.getByText("Enter your email")).toBeVisible();
  });

  test("register page redirects to login", async ({ page }) => {
    await page.goto("/register");
    await expect(page).toHaveURL("/login");
  });

  test("verify page shows error without token", async ({ page }) => {
    await page.goto("/auth/verify");
    await expect(
      page.getByText("Missing verification token")
    ).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Back to sign in")).toBeVisible();
  });
});
