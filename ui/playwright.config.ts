import { defineConfig, devices } from "@playwright/test";
import { getTarget, getTargetName } from "./e2e/config/targets";

/**
 * Playwright Configuration with Target-Based Modes
 *
 * Uses E2E_TARGET env var to select test environment:
 *
 *   npm run test:e2e           # mock mode (default) - fast, isolated
 *   npm run test:e2e:local     # test against local servers
 *   npm run test:e2e:remote    # test against remote dev/staging
 *
 * See e2e/config/targets.ts for full configuration details.
 */

const target = getTarget();
const isRealBackend = !target.useMocks;

// Log target for debugging
console.log(`\n🎯 E2E Target: ${target.name}`);
console.log(`   Base URL: ${target.baseUrl}`);
console.log(`   Mocks: ${target.useMocks ? "enabled" : "disabled"}`);
console.log(`   Auto-start server: ${target.startServer}\n`);

export default defineConfig({
  testDir: "./e2e/tests",

  // Global teardown ensures clean shutdown after all tests
  globalTeardown: "./e2e/global-teardown.ts",

  // In real backend mode, run sequentially to avoid race conditions
  fullyParallel: !isRealBackend,

  forbidOnly: !!process.env.CI,

  // More retries for real backend due to potential flakiness
  retries: isRealBackend ? 1 : process.env.CI ? 2 : 0,

  // Single worker for real backend to ensure consistent state
  workers: isRealBackend ? 1 : process.env.CI ? 1 : undefined,

  // Longer global timeout for real backend
  timeout: isRealBackend ? 60000 : 30000,

  // Longer expect timeout for real backend (actual API latency)
  expect: {
    timeout: isRealBackend ? 10000 : 5000,
  },

  reporter: [["html", { outputFolder: "playwright-report" }], ["list"]],

  use: {
    baseURL: target.baseUrl,
    trace: "on-first-retry",
    screenshot: "only-on-failure",

    // Timeouts from target config
    actionTimeout: target.timeout.action,
    navigationTimeout: target.timeout.navigation,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Only start dev server in mock mode
  webServer: target.startServer
    ? {
        command: "npm run dev",
        url: "http://localhost:5173",
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
      }
    : undefined,
});
