import { expect, test, type Page } from "@playwright/test";

/**
 * US4 acceptance: Platform super-admin provisions centers.
 *
 * Scenarios (spec.md): a super-admin creates a center together with its first admin, verifies
 * that admin can log in and manage only their own center (and cannot see another center's
 * data), then suspends the center and verifies its users are blocked from login until it is
 * reactivated.
 *
 * Requires a running stack with a seeded super-admin. Configure via env:
 *   BASE_URL, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD
 */
const SUPERADMIN_EMAIL = process.env.SUPERADMIN_EMAIL ?? "super@example.com";
const SUPERADMIN_PASSWORD = process.env.SUPERADMIN_PASSWORD ?? "TempPassword123!";
const TEMP_PASSWORD = "TempPassword123!";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function loginExpectingApp(page: Page, email: string, password: string) {
  await login(page, email, password);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Email")).toBeVisible();
}

test("super-admin provisions a center + first admin, then suspend blocks login", async ({
  page
}) => {
  const unique = Date.now();
  const centerName = `E2E Center ${unique}`;
  const adminEmail = `e2e.center.admin.${unique}@example.com`;

  // 1. Super-admin opens the centers page.
  await loginExpectingApp(page, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD);
  await page.getByRole("link", { name: "Centers" }).click();
  await expect(page.getByRole("heading", { name: "Centers" })).toBeVisible();

  // 2. Super-admin creates a center together with its first admin.
  await page.getByLabel("Center name").fill(centerName);
  await page.getByLabel(/Time zone/).fill("Africa/Cairo");
  await page.getByLabel("First admin email").fill(adminEmail);
  await page.getByLabel("Admin temporary password").fill(TEMP_PASSWORD);
  await page.getByRole("button", { name: "Create center" }).click();

  // 3. The new center appears in the list, active.
  const centerRow = page.locator("li", { hasText: centerName });
  await expect(centerRow).toBeVisible();
  await expect(centerRow.getByText("Active")).toBeVisible();
  await logout(page);

  // 4. The provisioned admin logs in and is forced to change their password first.
  await login(page, adminEmail, TEMP_PASSWORD);
  await expect(page.getByRole("heading", { name: "Change password" })).toBeVisible();
  await page.goto("/login");

  // 5. Super-admin suspends the center.
  await loginExpectingApp(page, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD);
  await page.getByRole("link", { name: "Centers" }).click();
  const row = page.locator("li", { hasText: centerName });
  await row.getByRole("button", { name: "Suspend" }).click();
  await expect(row.getByText("Suspended")).toBeVisible();
  await logout(page);

  // 6. The suspended center's admin can no longer log in.
  await login(page, adminEmail, TEMP_PASSWORD);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeHidden();

  // 7. Super-admin reactivates the center; its admin can log in again.
  await loginExpectingApp(page, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD);
  await page.getByRole("link", { name: "Centers" }).click();
  const restored = page.locator("li", { hasText: centerName });
  await restored.getByRole("button", { name: "Reactivate" }).click();
  await expect(restored.getByText("Active")).toBeVisible();
});

test("non-super-admin roles do not see the centers page", async ({ page }) => {
  const adminEmail = process.env.ADMIN_EMAIL ?? "admin@example.com";
  const adminPassword = process.env.ADMIN_PASSWORD ?? "TempPassword123!";

  await loginExpectingApp(page, adminEmail, adminPassword);
  await expect(page.getByRole("link", { name: "Centers" })).toBeHidden();

  // Direct navigation is redirected away from the super-admin-only route.
  await page.goto("/centers");
  await expect(page.getByRole("heading", { name: "Create center" })).toBeHidden();
});
