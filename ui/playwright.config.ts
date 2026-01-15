import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright Configuration with Dual-Mode Support
 *
 * Supports two test modes:
 * - Mock mode (default): Fast, isolated tests using route interception
 * - Integrated mode: Tests against real API backend
 *
 * Usage:
 *   npm run test:e2e              # Mock mode (default)
 *   npm run test:e2e:integrated   # Integrated mode
 *
 * Environment variables for integrated mode:
 *   TEST_MODE=integrated
 *   TEST_BASE_URL=http://localhost:5173
 *   TEST_ADMIN_USER=admin
 *   TEST_ADMIN_PASSWORD=admin123
 */

const isIntegrated = process.env.TEST_MODE === "integrated";

export default defineConfig({
  testDir: "./e2e/tests",

  // Global teardown ensures clean shutdown after all tests
  globalTeardown: "./e2e/global-teardown.ts",

  // In integrated mode, run sequentially to avoid race conditions
  fullyParallel: !isIntegrated,

  forbidOnly: !!process.env.CI,

  // More retries for integrated mode due to potential flakiness
  retries: isIntegrated ? 1 : process.env.CI ? 2 : 0,

  // Single worker for integrated mode to ensure consistent state
  workers: isIntegrated ? 1 : process.env.CI ? 1 : undefined,

  // Longer global timeout for integrated mode
  timeout: isIntegrated ? 60000 : 30000,

  // Longer expect timeout for integrated mode (real API latency)
  expect: {
    timeout: isIntegrated ? 10000 : 5000,
  },

  reporter: [["html", { outputFolder: "playwright-report" }], ["list"]],

  use: {
    baseURL: process.env.TEST_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",

    // Longer action timeout for integrated mode
    actionTimeout: isIntegrated ? 15000 : 5000,

    // Longer navigation timeout for integrated mode
    navigationTimeout: isIntegrated ? 30000 : 15000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Only start dev server in mock mode
  // In integrated mode, assume servers are already running
  webServer: isIntegrated
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:5173",
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
      },
});
