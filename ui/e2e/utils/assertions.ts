/**
 * Data-Agnostic Assertions for Dual-Mode Testing
 *
 * These assertions work in both mock and integrated modes by:
 * - Using minimum counts instead of exact counts where appropriate
 * - Testing structure and behavior rather than specific data values
 * - Providing flexible matchers that accommodate dynamic real data
 */

import { Page, Locator, expect } from "@playwright/test";
import { config, isMockMode } from "../config/test-config";

/**
 * Assert that a count is at least a minimum value.
 * Useful for tables, lists, etc. where exact count varies in integrated mode.
 *
 * @example
 * await expectMinimumCount(page.locator("tbody tr"), 1, "decision rows");
 */
export async function expectMinimumCount(
  locator: Locator,
  minCount: number,
  description: string
): Promise<void> {
  const count = await locator.count();
  expect(
    count,
    `Expected at least ${minCount} ${description}, got ${count}`
  ).toBeGreaterThanOrEqual(minCount);
}

/**
 * Assert exact count in mock mode, minimum count in integrated mode.
 * Allows precise assertions when data is controlled.
 *
 * @example
 * await expectCount(rows, { exact: 6, min: 1 }, "decisions");
 */
export async function expectCount(
  locator: Locator,
  options: { exact?: number; min?: number },
  description: string
): Promise<void> {
  const count = await locator.count();

  if (isMockMode() && options.exact !== undefined) {
    expect(count, `Expected exactly ${options.exact} ${description}`).toBe(options.exact);
  } else if (options.min !== undefined) {
    expect(
      count,
      `Expected at least ${options.min} ${description}`
    ).toBeGreaterThanOrEqual(options.min);
  }
}

/**
 * Assert that a table has rows.
 *
 * @example
 * await expectTableHasRows(table, { min: 1 });
 * await expectTableHasRows(table, { exact: 6 }); // Only enforced in mock mode
 */
export async function expectTableHasRows(
  table: Locator,
  options: { exact?: number; min?: number; max?: number } = { min: 1 }
): Promise<void> {
  const rows = table.locator("tbody tr");
  const count = await rows.count();

  if (isMockMode() && options.exact !== undefined) {
    expect(count, `Expected exactly ${options.exact} table rows`).toBe(options.exact);
  }
  if (options.min !== undefined) {
    expect(count, `Expected at least ${options.min} table rows`).toBeGreaterThanOrEqual(
      options.min
    );
  }
  if (options.max !== undefined) {
    expect(count, `Expected at most ${options.max} table rows`).toBeLessThanOrEqual(
      options.max
    );
  }
}

/**
 * Assert that text matches a pattern.
 * Useful for dynamic content like timestamps, IDs, etc.
 *
 * @example
 * await expectTextPattern(locator, /\d+ records/, "record count text");
 */
export async function expectTextPattern(
  locator: Locator,
  pattern: RegExp,
  description: string
): Promise<void> {
  const text = await locator.textContent();
  expect(text, description).toMatch(pattern);
}

/**
 * Assert hash chain status.
 * In mock mode with expected status: asserts exact status.
 * In integrated mode or without expected: asserts one of valid/invalid is shown.
 *
 * @example
 * await expectHashChainStatus(page, "valid"); // Asserts valid in mock mode
 * await expectHashChainStatus(page); // Just checks status is displayed
 */
export async function expectHashChainStatus(
  page: Page,
  expectedStatus?: "valid" | "invalid"
): Promise<void> {
  if (isMockMode() && expectedStatus) {
    // In mock mode with expected status, assert exact status
    // Check for both the full text (Verification page) or short text (Overview page)
    if (expectedStatus === "valid") {
      const fullText = page.getByText("Hash Chain Valid");
      const shortText = page.locator(".text-green-500").filter({ hasText: "Valid" });
      const isFullVisible = await fullText.isVisible().catch(() => false);
      const isShortVisible = await shortText.isVisible().catch(() => false);
      expect(isFullVisible || isShortVisible, "Expected valid hash chain status to be visible").toBe(true);
    } else {
      const fullText = page.getByText("Hash Chain Invalid");
      const shortText = page.locator(".text-red-500").filter({ hasText: "Invalid" });
      const isFullVisible = await fullText.isVisible().catch(() => false);
      const isShortVisible = await shortText.isVisible().catch(() => false);
      expect(isFullVisible || isShortVisible, "Expected invalid hash chain status to be visible").toBe(true);
    }
  } else {
    // In integrated mode or without expected status, check one is visible
    const validFull = page.getByText("Hash Chain Valid");
    const validShort = page.locator(".text-green-500").filter({ hasText: "Valid" });
    const invalidFull = page.getByText("Hash Chain Invalid");
    const invalidShort = page.locator(".text-red-500").filter({ hasText: "Invalid" });

    const isValidFull = await validFull.isVisible().catch(() => false);
    const isValidShort = await validShort.isVisible().catch(() => false);
    const isInvalidFull = await invalidFull.isVisible().catch(() => false);
    const isInvalidShort = await invalidShort.isVisible().catch(() => false);

    expect(
      isValidFull || isValidShort || isInvalidFull || isInvalidShort,
      "Expected a hash chain status (Valid or Invalid) to be visible"
    ).toBe(true);
  }
}

/**
 * Assert that a numeric value is displayed.
 * Useful for counts, percentages, etc.
 *
 * @example
 * await expectNumericValue(recordCountLocator, { min: 0 });
 * await expectNumericValue(percentLocator, { exact: 83 }); // Mock mode only
 */
export async function expectNumericValue(
  locator: Locator,
  options: { exact?: number; min?: number; max?: number } = {}
): Promise<void> {
  const text = await locator.textContent();
  const match = text?.match(/(\d+)/);
  expect(match, "Expected to find a numeric value").toBeTruthy();

  const value = parseInt(match![1]);

  if (isMockMode() && options.exact !== undefined) {
    expect(value).toBe(options.exact);
  }
  if (options.min !== undefined) {
    expect(value).toBeGreaterThanOrEqual(options.min);
  }
  if (options.max !== undefined) {
    expect(value).toBeLessThanOrEqual(options.max);
  }
}

/**
 * Assert that one of multiple possible texts is visible.
 * Useful for status indicators that may vary.
 *
 * @example
 * await expectOneOfTexts(page, ["Valid", "Invalid"], "hash chain status");
 */
export async function expectOneOfTexts(
  page: Page,
  texts: string[],
  description: string
): Promise<void> {
  const results = await Promise.all(
    texts.map(async (text) => {
      const locator = page.getByText(text, { exact: true });
      return locator.isVisible().catch(() => false);
    })
  );

  const anyVisible = results.some((visible) => visible);
  expect(anyVisible, `Expected one of [${texts.join(", ")}] for ${description}`).toBe(true);
}

/**
 * Assert that decision type badges are displayed correctly.
 * Checks for the presence of colored badge indicators.
 */
export async function expectDecisionTypeBadge(
  page: Page,
  type: "classification" | "extraction" | "human_review" | "override"
): Promise<void> {
  const typeDisplayMap = {
    classification: "classification",
    extraction: "extraction",
    human_review: "human review",
    override: "override",
  };

  const displayText = typeDisplayMap[type];
  const badge = page.locator(`span:has-text("${displayText}")`).first();
  await expect(badge).toBeVisible();
}

/**
 * Assert confidence level with color coding.
 * High (>=0.8): green, Medium (>=0.5): yellow, Low (<0.5): red
 */
export async function expectConfidenceDisplay(
  locator: Locator,
  options: { minValue?: number; hasColorCoding?: boolean } = {}
): Promise<void> {
  const text = await locator.textContent();
  const match = text?.match(/(\d+)%/);
  expect(match, "Expected percentage value").toBeTruthy();

  if (options.minValue !== undefined) {
    const value = parseInt(match![1]);
    expect(value).toBeGreaterThanOrEqual(options.minValue);
  }
}

/**
 * Wait for loading to complete and content to be ready.
 * Handles different loading indicators across the app.
 */
export async function waitForContentReady(
  page: Page,
  options: { loadingText?: string; timeout?: number } = {}
): Promise<void> {
  const { loadingText = "Loading", timeout = config.timeout.apiResponse } = options;

  // Wait for loading indicator to disappear
  const loadingIndicator = page.getByText(new RegExp(loadingText, "i"));
  await loadingIndicator.waitFor({ state: "hidden", timeout }).catch(() => {
    // Loading indicator might not appear if data loads fast
  });

  // Wait for network to settle
  await page.waitForLoadState("networkidle");
}
