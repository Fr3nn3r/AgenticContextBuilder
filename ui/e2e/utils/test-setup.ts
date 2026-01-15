/**
 * Abstract Test Setup Layer for Dual-Mode Testing
 *
 * Provides a unified interface for test setup that works in both:
 * - Mock mode: Sets up route interception with fixture data
 * - Integrated mode: Performs real login via UI
 */

import { Page, expect } from "@playwright/test";
import { config, isIntegratedMode, isMockMode } from "../config/test-config";
import {
  setupAuthenticatedMocks,
  setupComplianceMocks,
  type Role,
  type ComplianceMockOptions,
} from "./mock-api";

export { isIntegratedMode, isMockMode } from "../config/test-config";

/**
 * Unified test setup that works in both mock and integrated modes.
 *
 * @param page - Playwright page object
 * @param role - User role to authenticate as
 * @param options - Additional setup options
 */
export async function setupTestEnvironment(
  page: Page,
  role: Role = "admin",
  options: {
    complianceScenario?: "valid" | "invalid" | "empty";
    skipComplianceMocks?: boolean;
  } = {}
): Promise<void> {
  if (isMockMode()) {
    // Mock mode: set up route interception
    await setupAuthenticatedMocks(page, role);

    if (!options.skipComplianceMocks) {
      await setupComplianceMocks(page, {
        verification: options.complianceScenario || "valid",
      });
    }
  } else {
    // Integrated mode: perform real login
    await performRealLogin(page, role);
  }
}

/**
 * Setup test environment specifically for compliance testing with custom scenarios.
 * Use this when you need fine-grained control over compliance mock data.
 */
export async function setupComplianceTestEnvironment(
  page: Page,
  role: Role = "admin",
  complianceOptions: ComplianceMockOptions = {}
): Promise<void> {
  if (isMockMode()) {
    await setupAuthenticatedMocks(page, role);
    await setupComplianceMocks(page, complianceOptions);
  } else {
    await performRealLogin(page, role);
  }
}

/**
 * Perform actual login in integrated mode via the UI.
 */
async function performRealLogin(page: Page, role: Role): Promise<void> {
  const credentials = getCredentialsForRole(role);

  await page.goto("/login");
  await page.waitForLoadState("networkidle");

  await page.getByLabel("Username").fill(credentials.username);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: /sign in/i }).click();

  // Wait for redirect away from login page
  await expect(page).not.toHaveURL(/\/login/, {
    timeout: config.timeout.navigation,
  });

  // Wait for app to be ready
  await page.waitForLoadState("networkidle");
}

/**
 * Get credentials for a specific role from config.
 */
function getCredentialsForRole(role: Role): { username: string; password: string } {
  switch (role) {
    case "admin":
      return { username: config.auth.adminUser, password: config.auth.adminPassword };
    case "auditor":
      return { username: config.auth.auditorUser, password: config.auth.auditorPassword };
    case "reviewer":
      return { username: config.auth.reviewerUser, password: config.auth.reviewerPassword };
    case "operator":
      return { username: config.auth.operatorUser, password: config.auth.operatorPassword };
    default:
      throw new Error(`Unknown role: ${role}`);
  }
}

/**
 * Skip test in integrated mode.
 * Use for tests that require controlled mock data (e.g., invalid hash chain, empty states).
 *
 * @example
 * test("shows chain break location for invalid chain", async ({ page }) => {
 *   skipInIntegratedMode(test);
 *   // ... test code
 * });
 */
export function skipInIntegratedMode(
  testInstance: { skip: (condition: boolean, reason: string) => void },
  reason = "This test only runs in mock mode (requires controlled data)"
): void {
  testInstance.skip(isIntegratedMode(), reason);
}

/**
 * Skip test in mock mode.
 * Use for tests that only make sense with real data.
 *
 * @example
 * test("validates real compliance data integrity", async ({ page }) => {
 *   skipInMockMode(test);
 *   // ... test code
 * });
 */
export function skipInMockMode(
  testInstance: { skip: (condition: boolean, reason: string) => void },
  reason = "This test only runs in integrated mode (requires real data)"
): void {
  testInstance.skip(isMockMode(), reason);
}

/**
 * Get the appropriate timeout for the current test mode.
 */
export function getTimeout(type: "navigation" | "apiResponse" | "action"): number {
  return config.timeout[type];
}

/**
 * Get minimum expected counts for assertions based on test mode.
 */
export function getExpectations(): { minDecisionCount: number; minBundleCount: number } {
  return config.expectations;
}
