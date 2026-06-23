import { expect, test, type Page } from "@playwright/test";

/**
 * US3 acceptance: Center admin manages staff accounts.
 *
 * Scenarios (spec.md): a center-admin creates a doctor and a reception account (each issued a
 * temporary password, forced-change on first login), verifies each logs in with their own
 * credentials, and deactivates one — after which login is blocked while historical records
 * remain. The staff list shows only this center's users.
 *
 * Requires a running stack with the quickstart seed. Configure via env:
 *   BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD
 */
const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "TempPassword123!";
const TEMP_PASSWORD = "TempPassword123!";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function loginExpectingStaff(page: Page, email: string, password: string) {
  await login(page, email, password);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Email")).toBeVisible();
}

test("admin creates staff, new staff must change password, deactivation blocks login", async ({
  page
}) => {
  const unique = Date.now();
  const doctorEmail = `e2e.doctor.${unique}@example.com`;
  const doctorName = `Dr. E2E ${unique}`;

  // 1. Admin opens the staff page.
  await loginExpectingStaff(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Staff" }).click();
  await expect(page.getByRole("heading", { name: "Staff accounts" })).toBeVisible();

  // 2. Admin creates a doctor account with a temporary password.
  await page.getByLabel("Role").selectOption("doctor");
  await page.getByLabel("Display name").fill(doctorName);
  await page.getByLabel("Email").fill(doctorEmail);
  await page.getByLabel("Temporary password").fill(TEMP_PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();

  // 3. The new doctor appears in the center's staff list.
  await expect(page.getByText(doctorEmail)).toBeVisible();
  await logout(page);

  // 4. The new doctor logs in and is forced to change their password first.
  await login(page, doctorEmail, TEMP_PASSWORD);
  await expect(page.getByRole("heading", { name: "Change password" })).toBeVisible();
  await page.goto("/login");

  // 5. Admin deactivates the doctor.
  await loginExpectingStaff(page, ADMIN_EMAIL, ADMIN_PASSWORD);
  await page.getByRole("link", { name: "Staff" }).click();
  const row = page.locator("li", { hasText: doctorEmail });
  await row.getByRole("button", { name: "Deactivate" }).click();
  await expect(row.getByText("Inactive")).toBeVisible();
  await logout(page);

  // 6. The deactivated doctor can no longer log in.
  await login(page, doctorEmail, TEMP_PASSWORD);
  await expect(page.getByText("Invalid email or password.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeHidden();
});

test("non-admin roles do not see the staff page", async ({ page }) => {
  const receptionEmail = process.env.RECEPTION_EMAIL ?? "reception@example.com";
  const receptionPassword = process.env.RECEPTION_PASSWORD ?? "TempPassword123!";

  await loginExpectingStaff(page, receptionEmail, receptionPassword);
  await expect(page.getByRole("link", { name: "Staff" })).toBeHidden();

  // Direct navigation is redirected away from the admin-only route.
  await page.goto("/staff");
  await expect(page.getByRole("heading", { name: "Staff accounts" })).toBeHidden();
});
