/**
 * Compliance Integrated Smoke Tests
 *
 * These tests run against the real backend using mock authentication.
 * They detect error states on compliance pages.
 *
 * Run with: npx playwright test compliance-integrated-smoke
 *
 * Prerequisites:
 * - Backend running: uvicorn context_builder.api.main:app --reload --port 8000
 * - Frontend running: npm run dev (in ui folder)
 */

import { test, expect } from "@playwright/test";
import { setupTestEnvironment } from "../utils/test-setup";

// Error patterns to detect - these indicate something is broken
const ERROR_PATTERNS = [
  "Unknown error",
  "Failed to load",
  "Something went wrong",
  "Unable to",
  "Cannot connect",
  "Network error",
  "Server error",
  "Request failed",
];

test.describe("Compliance Integrated Smoke Tests", () => {
  // Use standard test setup for authentication
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
    // NOTE: Do NOT set up mocks - we want to hit real backend
  });

  /**
   * Check if page shows any error state
   */
  async function detectError(page: import("@playwright/test").Page): Promise<string | null> {
    await page.waitForLoadState("networkidle");

    // Check for known error text patterns
    for (const pattern of ERROR_PATTERNS) {
      const element = page.getByText(pattern, { exact: pattern === "Unknown error" });
      if (await element.isVisible().catch(() => false)) {
        return pattern;
      }
    }

    // Check for red/destructive error containers with error-like content
    const errorContainer = page.locator("[class*='destructive'], [class*='error'], .text-red-500");
    const count = await errorContainer.count();
    for (let i = 0; i < count; i++) {
      const text = await errorContainer.nth(i).textContent().catch(() => "");
      if (text && ERROR_PATTERNS.some((p) => text.toLowerCase().includes(p.toLowerCase()))) {
        return text.trim();
      }
    }

    return null;
  }

  test("compliance overview - loads without error", async ({ page }) => {
    await page.goto("/compliance");

    // FIRST check for errors - fail fast if error visible
    const error = await detectError(page);
    expect(error, `ERROR DETECTED: "${error}"`).toBeNull();

    // THEN verify expected content is visible
    await expect(
      page.getByRole("heading", { name: "Compliance Dashboard" }),
      "Page should show Compliance Dashboard heading"
    ).toBeVisible();
  });

  test("compliance ledger - loads without error", async ({ page }) => {
    await page.goto("/compliance/ledger");

    const error = await detectError(page);
    expect(error, `ERROR DETECTED: "${error}"`).toBeNull();

    await expect(
      page.getByRole("heading", { name: "Decision Ledger" }),
      "Page should show Decision Ledger heading"
    ).toBeVisible();
  });

  test("compliance verification - loads without error", async ({ page }) => {
    await page.goto("/compliance/verification");

    const error = await detectError(page);
    expect(error, `ERROR DETECTED: "${error}"`).toBeNull();

    await expect(
      page.getByRole("heading", { name: "Verification Center" }),
      "Page should show Verification Center heading"
    ).toBeVisible();
  });

  test("compliance version bundles - loads without error", async ({ page }) => {
    await page.goto("/compliance/version-bundles");

    const error = await detectError(page);
    expect(error, `ERROR DETECTED: "${error}"`).toBeNull();

    await expect(
      page.getByRole("heading", { name: "Version Bundles", exact: true }),
      "Page should show Version Bundles heading"
    ).toBeVisible();
  });

  test("compliance controls - loads without error", async ({ page }) => {
    await page.goto("/compliance/controls");

    const error = await detectError(page);
    expect(error, `ERROR DETECTED: "${error}"`).toBeNull();

    await expect(
      page.getByRole("heading", { name: "Control Mapping" }),
      "Page should show Control Mapping heading"
    ).toBeVisible();
  });

  test("all compliance pages - full smoke test", async ({ page }) => {
    const pages = [
      { url: "/compliance", name: "Overview", heading: "Compliance Dashboard" },
      { url: "/compliance/ledger", name: "Ledger", heading: "Decision Ledger" },
      { url: "/compliance/verification", name: "Verification", heading: "Verification Center" },
      { url: "/compliance/version-bundles", name: "Version Bundles", heading: "Version Bundles" },
      { url: "/compliance/controls", name: "Controls", heading: "Control Mapping" },
    ];

    const failures: string[] = [];

    for (const { url, name, heading } of pages) {
      await page.goto(url);

      // Check for error state
      const error = await detectError(page);
      if (error) {
        failures.push(`❌ ${name} (${url}): ERROR - "${error}"`);
        continue;
      }

      // Check for expected content
      const headingVisible = await page
        .getByRole("heading", { name: heading, exact: heading === "Version Bundles" })
        .isVisible({ timeout: 3000 })
        .catch(() => false);

      if (!headingVisible) {
        failures.push(`❌ ${name} (${url}): Missing heading "${heading}"`);
      }
    }

    expect(failures, `SMOKE TEST FAILURES:\n${failures.join("\n")}`).toHaveLength(0);
  });
});

