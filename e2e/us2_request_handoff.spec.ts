import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * US2 acceptance: Doctor sends an appointment request to reception.
 *
 * Scenarios (spec.md): a doctor submits a request (patient, reason, urgency, expected
 * duration); reception sees it queued (urgent/overdue highlighted) and fulfills it into a
 * concrete slot — the request becomes `fulfilled`, an appointment exists, and the doctor
 * receives an in-app notification. The decline path notifies the doctor with a reason.
 *
 * Requires a running stack with the quickstart seed. Configure via env:
 *   BASE_URL, RECEPTION_EMAIL, RECEPTION_PASSWORD, DOCTOR_EMAIL, DOCTOR_PASSWORD, DOCTOR_NAME
 */
const RECEPTION_EMAIL = process.env.RECEPTION_EMAIL ?? "reception@example.com";
const RECEPTION_PASSWORD = process.env.RECEPTION_PASSWORD ?? "TempPassword123!";
const DOCTOR_EMAIL = process.env.DOCTOR_EMAIL ?? "doctor@example.com";
const DOCTOR_PASSWORD = process.env.DOCTOR_PASSWORD ?? "TempPassword123!";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Email")).toBeVisible();
}

test("doctor requests, reception fulfills, doctor is notified", async ({ page, request }) => {
  // 1. Doctor submits an appointment request.
  await login(page, DOCTOR_EMAIL, DOCTOR_PASSWORD);
  await page.getByRole("link", { name: "Request appointment" }).click();
  await expect(page.getByRole("heading", { name: "Request an appointment" })).toBeVisible();
  await page.getByPlaceholder("Search name or phone").fill("a");
  await page.locator("ul button").first().click();
  await page.getByLabel("Reason / visit type").fill("Crown fitting");
  await page.getByLabel("Urgency").selectOption("urgent");
  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByText(/Request submitted/i)).toBeVisible();
  await logout(page);

  // 2. Reception sees the request in the pending queue (urgency highlighted) and fulfills it.
  await login(page, RECEPTION_EMAIL, RECEPTION_PASSWORD);
  await page.getByRole("link", { name: "Requests" }).click();
  await expect(page.getByRole("heading", { name: "Appointment requests" })).toBeVisible();
  await expect(page.getByText("Crown fitting")).toBeVisible();
  await page.getByRole("button", { name: "Fulfill" }).first().click();
  await expect(page.getByRole("heading", { name: "Fulfill request" })).toBeVisible();
  await page.getByLabel("Start").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByRole("heading", { name: "Fulfill request" })).toBeHidden();

  // 3. The request is fulfilled and a request-origin appointment exists (verified via API).
  await assertRequestFulfilled(request);

  // 4. The requesting doctor received a request_fulfilled notification.
  await logout(page);
  await login(page, DOCTOR_EMAIL, DOCTOR_PASSWORD);
  await assertDoctorNotified(request, "request_fulfilled");
});

test("reception declines a request with a reason and the doctor is notified", async ({
  page,
  request
}) => {
  // Doctor submits a request via the API for determinism.
  await login(page, DOCTOR_EMAIL, DOCTOR_PASSWORD);
  const patientId = await firstPatientId(request);
  const created = await request.post("/api/v1/requests", {
    data: {
      patient_id: patientId,
      reason: "Routine cleaning",
      urgency: "routine",
      expected_duration_minutes: 30
    }
  });
  expect(created.ok()).toBeTruthy();
  await logout(page);

  // Reception declines it with a reason.
  await login(page, RECEPTION_EMAIL, RECEPTION_PASSWORD);
  await page.getByRole("link", { name: "Requests" }).click();
  await page.getByRole("button", { name: "Decline" }).first().click();
  await expect(page.getByRole("heading", { name: "Decline request" })).toBeVisible();
  await page.getByPlaceholder("Reason for declining").fill("No capacity this week");
  await page.getByRole("button", { name: "Decline" }).click();
  await logout(page);

  // The doctor is notified of the decline.
  await login(page, DOCTOR_EMAIL, DOCTOR_PASSWORD);
  await assertDoctorNotified(request, "request_declined");
});

async function firstPatientId(request: APIRequestContext): Promise<string> {
  const list = await request.get("/api/v1/patients");
  expect(list.ok()).toBeTruthy();
  const patients = (await list.json()) as Array<{ id: string }>;
  expect(patients.length).toBeGreaterThan(0);
  return patients[0].id;
}

async function assertRequestFulfilled(request: APIRequestContext) {
  const list = await request.get("/api/v1/requests");
  expect(list.ok()).toBeTruthy();
  const requests = (await list.json()) as Array<{
    id: string;
    status: string;
    resulting_appointment_id: string | null;
  }>;
  const fulfilled = requests.filter((r) => r.status === "fulfilled");
  expect(fulfilled.length).toBeGreaterThan(0);
  expect(fulfilled[fulfilled.length - 1].resulting_appointment_id).toBeTruthy();
}

async function assertDoctorNotified(request: APIRequestContext, type: string) {
  const list = await request.get("/api/v1/notifications");
  expect(list.ok()).toBeTruthy();
  const notifications = (await list.json()) as Array<{ type: string }>;
  expect(notifications.some((n) => n.type === type)).toBeTruthy();
}
