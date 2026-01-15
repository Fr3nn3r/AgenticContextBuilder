/**
 * Compliance Smoke Tests
 *
 * These tests detect if compliance pages are showing error states.
 * They serve as early warning for backend issues, API failures,
 * or configuration problems that would cause user-visible errors.
 *
 * Run these tests against the real backend to catch integration issues.
 */

import { test, expect } from "@playwright/test";
import { setupTestEnvironment } from "../utils/test-setup";
import { setupComplianceMocks } from "../utils/mock-api";
import { isMockMode } from "../config/test-config";

test.describe("Compliance Smoke Tests", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
    if (isMockMode()) {
      await setupComplianceMocks(page);
    }
  });

  /**
   * Error detection - looks for actual error UI patterns, not just color classes
   */
  async function assertNoErrors(page: import("@playwright/test").Page, pageName: string) {
    // Wait for network to settle
    await page.waitForLoadState("networkidle");

    // Check for specific error message patterns (actual error text, not styling)
    const errorTextPatterns = [
      /^Unknown error$/i,        // Generic catch-all error
      /Failed to load/i,
      /Error:/i,
      /Something went wrong/i,
      /Unable to/i,
      /Cannot connect/i,
      /Network error/i,
      /Server error/i,
      /Request failed/i,
      /Not found/i,
      /Unauthorized/i,
      /Forbidden/i,
    ];

    for (const pattern of errorTextPatterns) {
      const errorElement = page.getByText(pattern).first();
      const isVisible = await errorElement.isVisible().catch(() => false);

      if (isVisible) {
        const errorText = await errorElement.textContent().catch(() => "unknown error");
        throw new Error(
          `Error detected on ${pageName}: "${errorText}" (matched pattern: ${pattern})`
        );
      }
    }

    // Check for error container with actual content (not just styled elements)
    // The error container in compliance pages has bg-destructive/10 AND contains error text
    const errorContainer = page.locator(".bg-destructive\\/10, [class*='bg-destructive']").filter({
      hasText: /(error|failed|unable|cannot)/i,
    });
    const hasErrorContainer = await errorContainer.count() > 0;

    if (hasErrorContainer) {
      const errorText = await errorContainer.first().textContent().catch(() => "unknown error");
      throw new Error(`Error container detected on ${pageName}: "${errorText}"`);
    }
  }

  test.describe("Page Load - No Errors", () => {
    test("compliance overview loads without errors", async ({ page }) => {
      await page.goto("/compliance");
      await assertNoErrors(page, "Compliance Overview");

      // Verify main content is visible (not just absence of errors)
      await expect(page.getByRole("heading", { name: "Compliance Dashboard" })).toBeVisible();
    });

    test("compliance ledger loads without errors", async ({ page }) => {
      await page.goto("/compliance/ledger");
      await assertNoErrors(page, "Compliance Ledger");

      await expect(page.getByRole("heading", { name: "Decision Ledger" })).toBeVisible();
    });

    test("compliance verification loads without errors", async ({ page }) => {
      await page.goto("/compliance/verification");
      await assertNoErrors(page, "Compliance Verification");

      await expect(page.getByRole("heading", { name: "Verification Center" })).toBeVisible();
    });

    test("compliance version bundles loads without errors", async ({ page }) => {
      await page.goto("/compliance/version-bundles");
      await assertNoErrors(page, "Compliance Version Bundles");

      await expect(page.getByRole("heading", { name: "Version Bundles", exact: true })).toBeVisible();
    });

    test("compliance controls loads without errors", async ({ page }) => {
      await page.goto("/compliance/controls");
      await assertNoErrors(page, "Compliance Controls");

      await expect(page.getByRole("heading", { name: "Control Mapping" })).toBeVisible();
    });
  });

  test.describe("API Response Validation", () => {
    test("verification API returns valid response", async ({ page }) => {
      // Track API responses
      let apiError: string | null = null;
      let apiResponse: unknown = null;

      page.on("response", async (response) => {
        if (response.url().includes("/api/compliance/ledger/verify")) {
          if (!response.ok()) {
            apiError = `API returned ${response.status()}: ${response.statusText()}`;
          } else {
            try {
              apiResponse = await response.json();
            } catch {
              apiError = "API response was not valid JSON";
            }
          }
        }
      });

      await page.goto("/compliance/verification");
      await page.waitForLoadState("networkidle");

      // In integrated mode, check the actual API response
      if (!isMockMode()) {
        expect(apiError, `Verification API error: ${apiError}`).toBeNull();
        expect(apiResponse).toBeTruthy();
      }

      await assertNoErrors(page, "Verification Page");
    });

    test("decisions API returns valid response", async ({ page }) => {
      let apiError: string | null = null;

      page.on("response", async (response) => {
        if (response.url().includes("/api/compliance/ledger/decisions")) {
          if (!response.ok()) {
            apiError = `API returned ${response.status()}: ${response.statusText()}`;
          }
        }
      });

      await page.goto("/compliance/ledger");
      await page.waitForLoadState("networkidle");

      if (!isMockMode()) {
        expect(apiError, `Decisions API error: ${apiError}`).toBeNull();
      }

      await assertNoErrors(page, "Ledger Page");
    });

    test("version bundles API returns valid response", async ({ page }) => {
      let apiError: string | null = null;

      page.on("response", async (response) => {
        if (response.url().includes("/api/compliance/version-bundles")) {
          if (!response.ok()) {
            apiError = `API returned ${response.status()}: ${response.statusText()}`;
          }
        }
      });

      await page.goto("/compliance/version-bundles");
      await page.waitForLoadState("networkidle");

      if (!isMockMode()) {
        expect(apiError, `Version Bundles API error: ${apiError}`).toBeNull();
      }

      await assertNoErrors(page, "Version Bundles Page");
    });
  });

  test.describe("Console Error Detection", () => {
    test("no JavaScript errors on compliance overview", async ({ page }) => {
      const consoleErrors: string[] = [];

      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(msg.text());
        }
      });

      page.on("pageerror", (error) => {
        consoleErrors.push(error.message);
      });

      await page.goto("/compliance");
      await page.waitForLoadState("networkidle");

      // Filter out known benign errors if any
      const realErrors = consoleErrors.filter(
        (err) => !err.includes("favicon") && !err.includes("404")
      );

      expect(
        realErrors,
        `JavaScript errors detected:\n${realErrors.join("\n")}`
      ).toHaveLength(0);
    });

    test("no JavaScript errors during compliance navigation", async ({ page }) => {
      const consoleErrors: string[] = [];

      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
        }
      });

      page.on("pageerror", (error) => {
        consoleErrors.push(`[pageerror] ${error.message}`);
      });

      // Navigate through all compliance pages
      const pages = [
        "/compliance",
        "/compliance/ledger",
        "/compliance/verification",
        "/compliance/version-bundles",
        "/compliance/controls",
      ];

      for (const url of pages) {
        await page.goto(url);
        await page.waitForLoadState("networkidle");
      }

      const realErrors = consoleErrors.filter(
        (err) => !err.includes("favicon") && !err.includes("404")
      );

      expect(
        realErrors,
        `JavaScript errors during navigation:\n${realErrors.join("\n")}`
      ).toHaveLength(0);
    });
  });
});
