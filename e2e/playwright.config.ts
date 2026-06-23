import { defineConfig, devices } from "@playwright/test";

/**
 * The SPA is served at BASE_URL (default Vite dev server). The backend is expected to be
 * running behind the same origin (Vite proxies /api/v1) with the quickstart seed applied:
 * a reception account, at least one doctor with weekly availability, and a patient.
 */
export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry"
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }]
});
