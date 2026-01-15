/**
 * E2E Test Target Configuration
 *
 * Single source of truth for test environment configuration.
 * Use E2E_TARGET env var to select the target:
 *
 *   E2E_TARGET=mock    # Fast tests with route interception (default)
 *   E2E_TARGET=local   # Test against locally running servers
 *   E2E_TARGET=remote  # Test against remote dev/staging environment
 *
 * For remote targets, also set:
 *   E2E_REMOTE_URL=https://dev.example.com
 *   E2E_USER=username
 *   E2E_PASS=password
 */

export type TargetName = "mock" | "local" | "remote";

export interface TargetConfig {
  name: TargetName;
  baseUrl: string;
  /** Whether Playwright should auto-start the dev server */
  startServer: boolean;
  /** Whether to use route interception for mock data */
  useMocks: boolean;
  /** Credentials for authentication (null if using mocks) */
  credentials: { user: string; pass: string } | null;
  /** Workspace name to activate (for remote/local tests) */
  workspaceName: string;
  /** Timeouts adjusted for target latency */
  timeout: {
    navigation: number;
    apiResponse: number;
    action: number;
  };
}

const targets: Record<TargetName, Omit<TargetConfig, "name">> = {
  /**
   * Mock mode: Fast, isolated tests using route interception.
   * Playwright auto-starts the dev server. No backend required.
   * Use for: CI, quick local iteration, testing UI logic.
   */
  mock: {
    baseUrl: "http://localhost:5173",
    startServer: true,
    useMocks: true,
    credentials: null,
    workspaceName: "",
    timeout: {
      navigation: 5000,
      apiResponse: 2000,
      action: 5000,
    },
  },

  /**
   * Local mode: Test against locally running servers.
   * You must start both backend and frontend yourself.
   * Use for: Testing real API integration locally.
   */
  local: {
    baseUrl: "http://localhost:5173",
    startServer: false,
    useMocks: false,
    credentials: {
      user: process.env.E2E_USER || "su",
      pass: process.env.E2E_PASS || "su",
    },
    workspaceName: process.env.E2E_WORKSPACE || "Integration Tests",
    timeout: {
      navigation: 15000,
      apiResponse: 10000,
      action: 15000,
    },
  },

  /**
   * Remote mode: Test against a deployed dev/staging environment.
   * Requires E2E_REMOTE_URL, E2E_USER, and E2E_PASS.
   * Use for: Validating deployments, remote debugging.
   */
  remote: {
    baseUrl: process.env.E2E_REMOTE_URL || "",
    startServer: false,
    useMocks: false,
    credentials: {
      user: process.env.E2E_USER || "",
      pass: process.env.E2E_PASS || "",
    },
    workspaceName: process.env.E2E_WORKSPACE || "Integration Tests",
    timeout: {
      navigation: 30000,
      apiResponse: 15000,
      action: 20000,
    },
  },
};

/**
 * Get the current target configuration based on E2E_TARGET env var.
 * Validates that required configuration is present.
 */
export function getTarget(): TargetConfig {
  const name = (process.env.E2E_TARGET || "mock") as TargetName;

  if (!targets[name]) {
    const available = Object.keys(targets).join(", ");
    throw new Error(
      `Unknown E2E_TARGET: "${name}". Available targets: ${available}`
    );
  }

  const target = { ...targets[name], name };

  // Validate remote target has required config
  if (name === "remote") {
    if (!target.baseUrl) {
      throw new Error(
        "E2E_TARGET=remote requires E2E_REMOTE_URL to be set.\n" +
          "Example: E2E_REMOTE_URL=https://dev.example.com npm run test:e2e:remote"
      );
    }
    if (!target.credentials?.user || !target.credentials?.pass) {
      throw new Error(
        "E2E_TARGET=remote requires E2E_USER and E2E_PASS to be set.\n" +
          "Example: E2E_USER=admin E2E_PASS=secret npm run test:e2e:remote"
      );
    }
  }

  return target;
}

/**
 * Check if currently running in mock mode.
 */
export function isMockMode(): boolean {
  return (process.env.E2E_TARGET || "mock") === "mock";
}

/**
 * Check if currently running against a real backend (local or remote).
 */
export function isRealBackend(): boolean {
  return !isMockMode();
}

/**
 * Get target name for logging/debugging.
 */
export function getTargetName(): TargetName {
  return (process.env.E2E_TARGET || "mock") as TargetName;
}
