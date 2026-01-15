/**
 * Test Configuration - Unified API for E2E tests
 *
 * This module re-exports from targets.ts and provides helper functions
 * for tests to access configuration in a consistent way.
 *
 * Usage:
 *   import { config, isMockMode } from '../config/test-config';
 */

import { getTarget, isMockMode, isRealBackend, type TargetConfig } from "./targets";

// Re-export for convenience
export { isMockMode, isRealBackend, getTargetName } from "./targets";

/**
 * Legacy type alias - prefer using TargetConfig from targets.ts
 * @deprecated Use TargetConfig from './targets' instead
 */
export type TestMode = "mock" | "integrated";

/**
 * Test configuration interface.
 * Maps target config to the format expected by existing tests.
 */
export interface TestConfig {
  mode: TestMode;
  apiBaseUrl: string;
  auth: {
    adminUser: string;
    adminPassword: string;
    auditorUser: string;
    auditorPassword: string;
    reviewerUser: string;
    reviewerPassword: string;
    operatorUser: string;
    operatorPassword: string;
  };
  timeout: {
    navigation: number;
    apiResponse: number;
    action: number;
  };
  expectations: {
    minDecisionCount: number;
    minBundleCount: number;
  };
}

/**
 * Get test configuration based on current target.
 * Maintains backward compatibility with existing test code.
 */
export function getTestConfig(): TestConfig {
  const target = getTarget();

  // Map target to legacy "mode" for backward compatibility
  const mode: TestMode = target.useMocks ? "mock" : "integrated";

  // Default credentials for mock mode
  const mockCredentials = {
    adminUser: "admin",
    adminPassword: "password",
    auditorUser: "auditor",
    auditorPassword: "password",
    reviewerUser: "reviewer",
    reviewerPassword: "password",
    operatorUser: "operator",
    operatorPassword: "password",
  };

  // Real credentials from env or defaults for local/remote
  const realCredentials = {
    adminUser: process.env.E2E_ADMIN_USER || process.env.E2E_USER || "su",
    adminPassword: process.env.E2E_ADMIN_PASS || process.env.E2E_PASS || "su",
    auditorUser: process.env.E2E_AUDITOR_USER || "tod",
    auditorPassword: process.env.E2E_AUDITOR_PASS || process.env.E2E_PASS || "su",
    reviewerUser: process.env.E2E_REVIEWER_USER || "ted",
    reviewerPassword: process.env.E2E_REVIEWER_PASS || process.env.E2E_PASS || "su",
    operatorUser: process.env.E2E_OPERATOR_USER || "seb",
    operatorPassword: process.env.E2E_OPERATOR_PASS || process.env.E2E_PASS || "su",
  };

  return {
    mode,
    apiBaseUrl: target.baseUrl,
    auth: target.useMocks ? mockCredentials : realCredentials,
    timeout: target.timeout,
    expectations: {
      // In mock mode we control the data, in real mode it may vary
      minDecisionCount: target.useMocks ? 1 : 0,
      minBundleCount: target.useMocks ? 1 : 0,
    },
  };
}

/** Singleton config instance */
export const config = getTestConfig();

/**
 * Check if running in integrated mode (backward compatibility).
 * @deprecated Use isRealBackend() from './targets' instead
 */
export function isIntegratedMode(): boolean {
  return isRealBackend();
}
