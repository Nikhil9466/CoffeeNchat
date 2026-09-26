import { test, expect, type Page } from "@playwright/test";
const api = process.env.COFFEENCHAT_API_URL || "http://127.0.0.1:8000";
const suffix = Date.now().toString(36);
const password = "BrowserPass123!";
async function register(page: Page, name: string) {
  await page.goto("/signup");
  await page.getByLabel("Username", { exact: true }).fill(name);
  await page.getByLabel("Email address").fill(name + "@example.com");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page).toHaveURL(/dashboard/);
}
test("two accounts: live messages, save, search, files, groups, mobile and logout", async ({
  browser,
}) => {
  const ctxA = await browser.newContext({
    viewport: { width: 1440, height: 950 },
  });
  const ctxB = await browser.newContext({
    viewport: { width: 1100, height: 850 },
  });
  const a = await ctxA.newPage(),
    b = await ctxB.newPage();
  const errors: string[] = [];
  a.on("pageerror", (e) => errors.push(e.message));
  b.on("pageerror", (e) => errors.push(e.message));
  const alice = "BrowserAlice" + suffix,
    bob = "BrowserBob" + suffix;
  await register(a, alice);
  await register(b, bob);
  await a
    .getByRole("button", { name: "New conversation", exact: true })
    .first()
    .click();
  await a
    .getByRole("textbox", { name: "Search people", exact: true })
    .fill(bob);
  await a.getByRole("button", { name: new RegExp(bob) }).click();
  await expect(
    a.getByRole("heading", { name: bob, exact: true }),
  ).toBeVisible();
  await a
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Hello from browser " + suffix);
  await a.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    b.getByRole("button", { name: new RegExp(alice) }),
  ).toBeVisible();
  await b.getByRole("button", { name: new RegExp(alice) }).click();
  await expect(
    b
      .getByRole("log")
      .getByText("Hello from browser " + suffix, { exact: true }),
  ).toBeVisible();
  await b
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Live reply received");
  await b.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    a.getByRole("log").getByText("Live reply received", { exact: true }),
  ).toBeVisible();
  await a
    .getByRole("button", { name: "Save message", exact: true })
    .last()
    .click();
  await a.getByRole("button", { name: "Saved messages", exact: true }).click();
  await expect(
    a.getByRole("log").getByText("Live reply received", { exact: true }),
  ).toBeVisible();
  await a.getByRole("button", { name: "Unsave message", exact: true }).click();
  await expect(a.getByText("Nothing saved yet")).toBeVisible();
  await a.getByRole("button", { name: "Conversations", exact: true }).click();
  await a.getByRole("button", { name: new RegExp(bob) }).click();
  await a
    .getByRole("textbox", { name: "Search this conversation" })
    .fill("Live reply");
  await a
    .getByRole("textbox", { name: "Search this conversation" })
    .press("Enter");
  await expect(
    a.getByRole("log").getByText("Live reply received", { exact: true }),
  ).toBeVisible();
  await a.getByRole("button", { name: "Clear results", exact: true }).click();
  await a
    .locator("input[type=file]")
    .setInputFiles({
      name: "browser-note.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("verified private file"),
    });
  await expect(b.getByRole("link", { name: /browser-note.txt/ })).toBeVisible();
  await a.screenshot({
    path: "test-results/desktop-chat.png",
    fullPage: true,
    animations: "disabled",
  });
  await b.setViewportSize({ width: 390, height: 844 });
  await b.getByRole("button", { name: "Open conversations" }).click();
  await expect(
    b.getByRole("textbox", { name: "Search conversations" }),
  ).toBeVisible();
  await b.getByRole("button", { name: new RegExp(alice) }).click();
  await expect(
    b.getByRole("textbox", { name: "Message", exact: true }),
  ).toBeVisible();
  expect(
    await b.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await b.screenshot({
    path: "test-results/mobile-chat.png",
    fullPage: true,
    animations: "disabled",
  });
  await a
    .getByRole("button", { name: "New conversation", exact: true })
    .first()
    .click();
  await a.getByRole("button", { name: "New group", exact: true }).click();
  await a.getByLabel("Group name").fill("Browser team " + suffix);
  await a
    .getByRole("textbox", { name: "Search people", exact: true })
    .fill(bob);
  await a
    .getByRole("dialog")
    .getByRole("button", { name: new RegExp(bob) })
    .click();
  await a.getByRole("button", { name: /Create group/ }).click();
  await a
    .getByRole("button", { name: "Conversation details", exact: true })
    .click();
  await expect(a.getByText("2 people in this group")).toBeVisible();
  await a.getByRole("link", { name: "Your profile", exact: true }).click();
  await expect(
    a.getByText("Connected sessions", { exact: true }),
  ).toBeVisible();
  await a.getByLabel("A little about you").fill("Browser-verified profile");
  await a.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(a.getByText("Profile updated", { exact: true })).toBeVisible();
  await a.screenshot({
    path: "test-results/profile.png",
    fullPage: true,
    animations: "disabled",
  });
  await a
    .getByRole("button", { name: "Sign out of this browser", exact: true })
    .click();
  await expect(a).toHaveURL(/login/);
  expect((await ctxA.request.get(api + "/users/me")).status()).toBe(401);
  expect(errors).toEqual([]);
  await ctxA.close();
  await ctxB.close();
});

test("an unconfirmed send retries once without duplicating the committed message; history survives reload", async ({
  page,
}) => {
  const name = "RetryUser" + Date.now().toString(36);
  await register(page, name);
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "New group", exact: true }).click();
  await page.getByLabel("Group name").fill("Retry verification");
  await page.getByRole("button", { name: /Create group/ }).click();
  await page.route("**/api/conversations/*/messages", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Simulated lost response" }),
    });
    await page.unroute("**/api/conversations/*/messages");
  });
  await page
    .getByRole("textbox", { name: "Message", exact: true })
    .fill("Retry should not duplicate");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Retry message", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Retry message", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Send message", exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /Retry verification/ }).click();
  await expect(
    page
      .getByRole("log")
      .getByText("Retry should not duplicate", { exact: true }),
  ).toHaveCount(1);
  await page
    .getByRole("button", { name: "Use light appearance", exact: true })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({
    path: "test-results/light-chat.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("landing and authentication layouts fit a narrow screen", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.screenshot({
    path: "test-results/landing.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.goto("/login");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/mobile-login.png",
    fullPage: true,
    animations: "disabled",
  });
});
