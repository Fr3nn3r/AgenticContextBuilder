/**
 * Test Setup Utilities for E2E Testing
 *
 * Provides a unified interface for test setup that works across all targets:
 * - mock: Sets up route interception with fixture data
 * - local/remote: Performs real login via UI
 */

import { Page, expect } from "@playwright/test";
import { getTarget, isMockMode, isRealBackend } from "../config/targets";
import { config } from "../config/test-config";
import {
  setupAuthenticatedMocks,
  setupComplianceMocks,
  type Role,
  type ComplianceMockOptions,
} from "./mock-api";

// Re-export for convenience
export { isMockMode, isRealBackend } from "../config/targets";

/**
 * @deprecated Use isRealBackend() instead
 */
export function isIntegratedMode(): boolean {
  return isRealBackend();
}

/**
 * Unified test setup that works across all targets.
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
    // Real backend (local or remote): perform actual login
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
 * Perform actual login via the UI.
 * Used for local and remote targets.
 */
async function performRealLogin(page: Page, role: Role): Promise<void> {
  const credentials = getCredentialsForRole(role);
  const target = getTarget();

  await page.goto("/login");
  await page.waitForLoadState("networkidle");

  await page.getByLabel("Username").fill(credentials.username);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: /sign in/i }).click();

  // Wait for redirect away from login page
  await expect(page).not.toHaveURL(/\/login/, {
    timeout: target.timeout.navigation,
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
 * Skip test in real backend mode (local or remote).
 * Use for tests that require controlled mock data.
 *
 * @example
 * test("shows chain break location for invalid chain", async ({ page }) => {
 *   skipInRealBackendMode(test);
 *   // ... test code that requires mock data
 * });
 */
export function skipInRealBackendMode(
  testInstance: { skip: (condition: boolean, reason: string) => void },
  reason = "This test only runs in mock mode (requires controlled data)"
): void {
  testInstance.skip(isRealBackend(), reason);
}

/**
 * @deprecated Use skipInRealBackendMode() instead
 */
export function skipInIntegratedMode(
  testInstance: { skip: (condition: boolean, reason: string) => void },
  reason = "This test only runs in mock mode (requires controlled data)"
): void {
  skipInRealBackendMode(testInstance, reason);
}

/**
 * Skip test in mock mode.
 * Use for tests that only make sense with real data.
 *
 * @example
 * test("validates real compliance data integrity", async ({ page }) => {
 *   skipInMockMode(test);
 *   // ... test code that requires real backend
 * });
 */
export function skipInMockMode(
  testInstance: { skip: (condition: boolean, reason: string) => void },
  reason = "This test only runs against real backend (requires real data)"
): void {
  testInstance.skip(isMockMode(), reason);
}

/**
 * Get the appropriate timeout for the current target.
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
