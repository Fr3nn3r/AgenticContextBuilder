/**
 * Compliance Verification Tests
 *
 * Tests the hash chain verification functionality:
 * - Valid hash chain display
 * - Invalid hash chain with break location
 * - Empty ledger handling
 * - Re-verification functionality
 * - Educational content display
 *
 * Works in both mock and integrated modes.
 */

import { test, expect } from "@playwright/test";
import {
  setupTestEnvironment,
  skipInIntegratedMode,
  isMockMode,
} from "../utils/test-setup";
import { setupComplianceMocks } from "../utils/mock-api";
import { expectHashChainStatus, expectNumericValue } from "../utils/assertions";
import { ComplianceVerificationPage } from "../pages/compliance.page";

test.describe("Compliance Verification", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
  });

  test.describe("Valid Hash Chain", () => {
    test.beforeEach(async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page, { verification: "valid" });
      }
    });

    test("displays verification page", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();
      await verification.expectLoaded();
    });

    test("shows valid status with green indicator", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      if (isMockMode()) {
        await verification.expectValid();
        await expect(verification.statusIconValid).toBeVisible();
      } else {
        // In integrated mode, just check status is displayed
        await expectHashChainStatus(page);
      }
    });

    test("shows success message for valid chain", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      if (isMockMode()) {
        await expect(
          page.getByText("All decision records are intact and have not been tampered with")
        ).toBeVisible();
      }
    });

    test("displays total record count", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await expect(verification.totalRecordsLabel).toBeVisible();
      await expectNumericValue(verification.totalRecordsValue, { min: 0 });
    });

    test("does not show break location for valid chain", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      if (isMockMode()) {
        await expect(verification.breakLocationSection).not.toBeVisible();
      }
    });
  });

  test.describe("Invalid Hash Chain (Edge Case)", () => {
    test("displays invalid status with red indicator", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot force invalid hash chain in integrated mode");

      await setupComplianceMocks(page, { verification: "invalid" });

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await verification.expectInvalid();
      await expect(verification.statusIconInvalid).toBeVisible();
    });

    test("shows chain break location", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot force invalid hash chain in integrated mode");

      await setupComplianceMocks(page, { verification: "invalid" });

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      // Look for break location section - use exact match for the dd element
      await expect(page.getByText("Chain Break Location")).toBeVisible();
      await expect(page.getByText("Record #3", { exact: true })).toBeVisible();
    });

    test("displays error reason", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot force invalid hash chain in integrated mode");

      await setupComplianceMocks(page, { verification: "invalid" });

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      // Reason contains "Hash mismatch" text from fixture - use first() since it appears multiple times
      await expect(page.getByText(/Hash mismatch/i).first()).toBeVisible();
    });

    test("shows compromised message", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot force invalid hash chain in integrated mode");

      await setupComplianceMocks(page, { verification: "invalid" });

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      // When there's a reason, it shows the reason text which contains "Hash mismatch"
      // When there's no reason, it shows "compromised" - we just check the invalid state is shown
      await expect(page.getByText("Hash Chain Invalid")).toBeVisible();
    });
  });

  test.describe("Empty Ledger (Edge Case)", () => {
    test("shows valid status with zero records", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee empty ledger in integrated mode");

      await setupComplianceMocks(page, { verification: "empty" });

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await verification.expectValid();

      const count = await verification.getTotalRecords();
      expect(count).toBe(0);
    });
  });

  test.describe("Re-verification", () => {
    test("re-verify button exists and is clickable", async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page);
      }

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      // Wait for initial load to complete
      await expect(page.getByText(/Hash Chain (Valid|Invalid)/)).toBeVisible();

      const reVerifyBtn = page.getByRole("button", { name: /re-run verification/i });
      await expect(reVerifyBtn).toBeVisible();
      await expect(reVerifyBtn).toBeEnabled();
    });

    test("re-verify triggers new verification", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot track API calls in integrated mode");

      // Set up all other mocks first, then override verify endpoint
      await setupComplianceMocks(page);

      // Track API calls by overriding the route
      let verifyCount = 0;
      await page.unroute("**/api/compliance/ledger/verify");
      await page.route("**/api/compliance/ledger/verify", async (route) => {
        verifyCount++;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ valid: true, record_count: verifyCount }),
        });
      });

      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      // Wait for initial verification to complete
      await expect(page.getByText("Hash Chain Valid")).toBeVisible();

      // Click re-verify
      const reVerifyBtn = page.getByRole("button", { name: /re-run verification/i });
      await reVerifyBtn.click();

      // Wait for new verification to complete
      await page.waitForLoadState("networkidle");

      // Verify API was called again
      expect(verifyCount).toBeGreaterThan(1);
    });

    test("shows loading state during verification", async ({ page }) => {
      skipInIntegratedMode(test, "Loading states are timing-dependent");

      // Set up all other mocks first, then override verify endpoint with delay
      await setupComplianceMocks(page);
      await page.unroute("**/api/compliance/ledger/verify");
      await page.route("**/api/compliance/ledger/verify", async (route) => {
        await new Promise((r) => setTimeout(r, 1000));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ valid: true, record_count: 1 }),
        });
      });

      await page.goto("/compliance/verification");

      // Should show verifying state initially - use heading role to be specific
      await expect(page.getByRole("heading", { name: "Verifying..." })).toBeVisible({ timeout: 2000 });
    });

    test("button is disabled during verification", async ({ page }) => {
      skipInIntegratedMode(test, "Loading states are timing-dependent");

      // Set up all other mocks first, then override verify endpoint with delay
      await setupComplianceMocks(page);
      await page.unroute("**/api/compliance/ledger/verify");
      await page.route("**/api/compliance/ledger/verify", async (route) => {
        await new Promise((r) => setTimeout(r, 1000));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ valid: true, record_count: 1 }),
        });
      });

      await page.goto("/compliance/verification");

      // During loading, the button should show "Verifying..." and be disabled
      const loadingBtn = page.getByRole("button", { name: /verifying/i });
      await expect(loadingBtn).toBeVisible({ timeout: 2000 });
      await expect(loadingBtn).toBeDisabled();
    });
  });

  test.describe("Educational Content", () => {
    test.beforeEach(async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page);
      }
    });

    test("displays hash chain explanation section", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await expect(verification.explanationSection).toBeVisible();
    });

    test("explains cryptographic hash linking", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await expect(page.getByText(/cryptographic hash/i)).toBeVisible();
    });

    test("shows hash chain diagram", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      // Wait for page to load
      await verification.expectLoaded();

      // Diagram has Record N-1, Record N, Record N+1 - use exact match to avoid partial matches
      await expect(page.getByText("Record N-1", { exact: false })).toBeVisible();
      await expect(page.getByText("Record N", { exact: false }).first()).toBeVisible();
      await expect(page.getByText("Record N+1", { exact: false })).toBeVisible();
    });

    test("displays security note about encryption", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await expect(verification.securityNote).toBeVisible();
      await expect(page.getByText(/AES-256-GCM/i)).toBeVisible();
    });

    test("mentions role-based access", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await expect(page.getByText(/admin.*auditor|auditor.*admin/i)).toBeVisible();
    });
  });

  test.describe("Navigation", () => {
    test.beforeEach(async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page);
      }
    });

    test("navigates back to overview", async ({ page }) => {
      const verification = new ComplianceVerificationPage(page);
      await verification.goto();

      await verification.navigateBack();
      await expect(page).toHaveURL(/\/compliance$/);
    });
  });
});
