/**
 * Test Configuration Layer for Dual-Mode Testing
 *
 * Supports two modes:
 * - "mock": Fast, deterministic tests using route interception (default)
 * - "integrated": Tests against real API with actual backend
 *
 * Usage:
 *   TEST_MODE=integrated npm run test:e2e
 */

export type TestMode = "mock" | "integrated";

export interface TestConfig {
  mode: TestMode;
  apiBaseUrl: string;
  /** Credentials for different roles in integrated mode */
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
  /** Timeouts - longer for integrated mode due to real API latency */
  timeout: {
    navigation: number;
    apiResponse: number;
    action: number;
  };
  /** Minimum expected data counts for integrated mode assertions */
  expectations: {
    minDecisionCount: number;
    minBundleCount: number;
  };
}

const mockConfig: TestConfig = {
  mode: "mock",
  apiBaseUrl: "http://localhost:5173",
  auth: {
    adminUser: "admin",
    adminPassword: "password",
    auditorUser: "auditor",
    auditorPassword: "password",
    reviewerUser: "reviewer",
    reviewerPassword: "password",
    operatorUser: "operator",
    operatorPassword: "password",
  },
  timeout: {
    navigation: 5000,
    apiResponse: 2000,
    action: 5000,
  },
  expectations: {
    minDecisionCount: 1,
    minBundleCount: 1,
  },
};

const integratedConfig: TestConfig = {
  mode: "integrated",
  apiBaseUrl: process.env.TEST_BASE_URL || "http://localhost:5173",
  auth: {
    // Default credentials match backend's default users (see users.py)
    adminUser: process.env.TEST_ADMIN_USER || "su",
    adminPassword: process.env.TEST_ADMIN_PASSWORD || "su",
    auditorUser: process.env.TEST_AUDITOR_USER || "tod",
    auditorPassword: process.env.TEST_AUDITOR_PASSWORD || "su",
    reviewerUser: process.env.TEST_REVIEWER_USER || "ted",
    reviewerPassword: process.env.TEST_REVIEWER_PASSWORD || "su",
    operatorUser: process.env.TEST_OPERATOR_USER || "seb",
    operatorPassword: process.env.TEST_OPERATOR_PASSWORD || "su",
  },
  timeout: {
    navigation: 15000,
    apiResponse: 10000,
    action: 15000,
  },
  expectations: {
    minDecisionCount: 0, // May be 0 if no pipeline runs yet
    minBundleCount: 0,
  },
};

export function getTestConfig(): TestConfig {
  const mode = (process.env.TEST_MODE as TestMode) || "mock";
  return mode === "integrated" ? integratedConfig : mockConfig;
}

/** Singleton config instance */
export const config = getTestConfig();

/** Helper to check current mode */
export function isMockMode(): boolean {
  return config.mode === "mock";
}

/** Helper to check current mode */
export function isIntegratedMode(): boolean {
  return config.mode === "integrated";
}
