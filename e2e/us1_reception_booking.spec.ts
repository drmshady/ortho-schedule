import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * US1 acceptance: Reception schedules patient appointments.
 *
 * Scenarios (spec.md): reception finds/registers a patient, books an open slot into a doctor's
 * grid, the booking appears on the day view, a second booking of the same doctor/slot is
 * blocked with `double_booking`, and reception can reschedule and cancel.
 *
 * Requires a running stack with the quickstart seed. Configure via env:
 *   BASE_URL, RECEPTION_EMAIL, RECEPTION_PASSWORD, DOCTOR_NAME
 */
const RECEPTION_EMAIL = process.env.RECEPTION_EMAIL ?? "reception@example.com";
const RECEPTION_PASSWORD = process.env.RECEPTION_PASSWORD ?? "TempPassword123!";
const DOCTOR_NAME = process.env.DOCTOR_NAME ?? "Dr. Example";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(RECEPTION_EMAIL);
  await page.getByLabel("Password").fill(RECEPTION_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: /Reception — day view/ })).toBeVisible();
}

async function openBookingModal(page: Page) {
  await page.getByLabel("Doctor").selectOption({ label: DOCTOR_NAME });
  await page.getByRole("button", { name: "Book" }).click();
  await expect(page.getByRole("heading", { name: "Book appointment" })).toBeVisible();
}

/** Pick the first patient match and the first open slot, then confirm. Returns the chosen slot label. */
async function bookFirstOpenSlot(page: Page): Promise<string> {
  await page.getByPlaceholder("Search name or phone").fill("a");
  await page.locator("ul button").first().click();

  const startSelect = page.getByLabel("Start");
  await expect(startSelect.locator("option")).not.toHaveCount(1); // more than the "Select…" placeholder
  const slotLabel = (await startSelect.locator("option").nth(1).textContent()) ?? "";
  await startSelect.selectOption({ index: 1 });
  await page.getByRole("button", { name: "Confirm" }).click();
  return slotLabel;
}

test("reception books a patient, the slot is protected, and can reschedule/cancel", async ({
  page,
  request
}) => {
  await login(page);

  // 1. Book an appointment for a patient into an open slot.
  await openBookingModal(page);
  await bookFirstOpenSlot(page);
  await expect(page.getByRole("heading", { name: "Book appointment" })).toBeHidden();

  // 2. The booking shows on the reception day view.
  await expect(page.locator(".fc-event").first()).toBeVisible();

  // 3. Booking the exact same doctor/slot again is blocked with a double-booking message.
  await openBookingModal(page);
  await page.getByPlaceholder("Search name or phone").fill("a");
  await page.locator("ul button").first().click();
  await page.getByLabel("Start").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText(/just taken/i)).toBeVisible();

  // 4. Reschedule and cancel are exercised through the tenant-scoped API (shared session cookie).
  await rescheduleAndCancelLatest(request);
});

/** Reschedule the most recent scheduled appointment by 15 minutes, then cancel it. */
async function rescheduleAndCancelLatest(request: APIRequestContext) {
  const list = await request.get("/api/v1/appointments");
  expect(list.ok()).toBeTruthy();
  const appointments = (await list.json()) as Array<{
    id: string;
    starts_at: string;
    duration_minutes: number;
    status: string;
  }>;
  const scheduled = appointments.filter((a) => a.status === "scheduled");
  expect(scheduled.length).toBeGreaterThan(0);
  const target = scheduled[scheduled.length - 1];

  const moved = new Date(new Date(target.starts_at).getTime() + 15 * 60_000).toISOString();
  const reschedule = await request.post(`/api/v1/appointments/${target.id}/reschedule`, {
    data: { starts_at: moved, duration_minutes: target.duration_minutes }
  });
  expect(reschedule.ok()).toBeTruthy();

  const cancel = await request.put(`/api/v1/appointments/${target.id}/status`, {
    data: { status: "cancelled", cancel_reason: "patient request" }
  });
  expect(cancel.ok()).toBeTruthy();
  expect((await cancel.json()).status).toBe("cancelled");
}
