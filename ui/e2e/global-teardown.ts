/**
 * Playwright Global Teardown
 *
 * Runs after all tests complete to ensure clean shutdown.
 * Helps prevent connection accumulation from incomplete test runs.
 */

import type { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig): Promise<void> {
  console.log('[teardown] Cleaning up test resources...');

  // Give browsers a moment to close their connections gracefully
  await new Promise((resolve) => setTimeout(resolve, 500));

  console.log('[teardown] Complete');
}

export default globalTeardown;
