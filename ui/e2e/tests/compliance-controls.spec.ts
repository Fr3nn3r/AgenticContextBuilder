/**
 * Compliance Controls Tests
 *
 * Tests the control mapping page:
 * - Progress indicator display
 * - Control categories and status
 * - Sub-item status indicators
 * - Navigation links to related pages
 * - Demo talking points
 *
 * Works in both mock and integrated modes.
 * Note: Controls page is static content, works identically in both modes.
 */

import { test, expect } from "@playwright/test";
import { setupTestEnvironment, isMockMode } from "../utils/test-setup";
import { setupComplianceMocks } from "../utils/mock-api";
import { ComplianceControlsPage } from "../pages/compliance.page";

test.describe("Compliance Controls", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
    if (isMockMode()) {
      await setupComplianceMocks(page);
    }
  });

  test.describe("Page Layout", () => {
    test("displays control mapping page", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();
      await controls.expectLoaded();
    });

    test("shows page description", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(
        page.getByText("How ContextBuilder maps to audit-first compliance requirements")
      ).toBeVisible();
    });
  });

  test.describe("Progress Indicator", () => {
    test("displays progress percentage", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectProgressPercentage(83);
    });

    test("shows implementation count", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(controls.implementedCount).toBeVisible();
      await expect(page.getByText(/5 of 6 control categories/i)).toBeVisible();
    });

    test("shows audit-first minimum label", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Audit-First Minimum")).toBeVisible();
    });
  });

  test.describe("Control Categories", () => {
    test("displays all six control categories", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      // Use heading role to avoid matching talking points text
      await expect(page.getByRole("heading", { name: "Decision Capture" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Tamper Evidence" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Version Control" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Human Oversight" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Access Control" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "Evidence Export" })).toBeVisible();
    });

    test("shows implemented status for Decision Capture", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectCategoryStatus("Decision Capture", "Implemented");
    });

    test("shows implemented status for Tamper Evidence", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectCategoryStatus("Tamper Evidence", "Implemented");
    });

    test("shows implemented status for Version Control", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectCategoryStatus("Version Control", "Implemented");
    });

    test("shows implemented status for Human Oversight", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectCategoryStatus("Human Oversight", "Implemented");
    });

    test("shows implemented status for Access Control", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectCategoryStatus("Access Control", "Implemented");
    });

    test("shows planned status for Evidence Export", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectCategoryStatus("Evidence Export", "Planned");
    });
  });

  test.describe("Sub-Items", () => {
    test("displays Decision Capture sub-items", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      // Sub-items are in list items within control cards
      const decisionCaptureCard = page.locator(".bg-card").filter({ hasText: "Decision Capture" });
      await expect(decisionCaptureCard.getByText("Classification decisions")).toBeVisible();
      await expect(decisionCaptureCard.getByText("Extraction decisions")).toBeVisible();
      await expect(decisionCaptureCard.getByText("Human reviews")).toBeVisible();
      await expect(decisionCaptureCard.getByText("Override actions")).toBeVisible();
    });

    test("displays Tamper Evidence sub-items", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      // Sub-items are in list items within control cards
      const tamperEvidenceCard = page.locator(".bg-card").filter({ hasText: "Tamper Evidence" });
      await expect(tamperEvidenceCard.getByText("Hash chain linking")).toBeVisible();
      await expect(tamperEvidenceCard.getByText("Integrity verification")).toBeVisible();
      await expect(tamperEvidenceCard.getByText("AES-256-GCM encryption")).toBeVisible();
    });

    test("displays Version Control sub-items", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Git commit tracking")).toBeVisible();
      await expect(page.getByText("Model version capture")).toBeVisible();
      await expect(page.getByText("Prompt template hashing")).toBeVisible();
      await expect(page.getByText("Extraction spec hashing")).toBeVisible();
    });

    test("displays Evidence Export sub-items as planned", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Decision export (JSON/CSV)")).toBeVisible();
      await expect(page.getByText("Evidence pack generation")).toBeVisible();
      await expect(page.getByText("Bulk audit reports")).toBeVisible();
    });

    test("shows 'View' links for completed items", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      const viewLinks = page.getByRole("link", { name: "View →" });
      const count = await viewLinks.count();
      expect(count).toBeGreaterThan(0);
    });

    test("shows 'Coming soon' for planned items", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      const comingSoon = page.getByText("Coming soon");
      const count = await comingSoon.count();
      expect(count).toBeGreaterThan(0);
    });
  });

  test.describe("Navigation Links", () => {
    test("classification decisions link goes to filtered ledger", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      const classificationItem = page.locator("li").filter({ hasText: "Classification decisions" });
      await classificationItem.getByRole("link", { name: "View →" }).click();

      await expect(page).toHaveURL(/\/compliance\/ledger\?type=classification/);
    });

    test("extraction decisions link goes to filtered ledger", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      const extractionItem = page.locator("li").filter({ hasText: "Extraction decisions" });
      await extractionItem.getByRole("link", { name: "View →" }).click();

      await expect(page).toHaveURL(/\/compliance\/ledger\?type=extraction/);
    });

    test("hash chain linking link goes to verification", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      const hashChainItem = page.locator("li").filter({ hasText: "Hash chain linking" });
      await hashChainItem.getByRole("link", { name: "View →" }).click();

      await expect(page).toHaveURL(/\/compliance\/verification/);
    });

    test("git commit tracking link goes to version bundles", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      const gitItem = page.locator("li").filter({ hasText: "Git commit tracking" });
      await gitItem.getByRole("link", { name: "View →" }).click();

      await expect(page).toHaveURL(/\/compliance\/version-bundles/);
    });
  });

  test.describe("Demo Talking Points", () => {
    test("displays talking points section", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.expectTalkingPoints();
    });

    test("shows tamper-evident audit trail point", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Tamper-evident audit trail")).toBeVisible();
      await expect(page.getByText(/cryptographic hash chain/i)).toBeVisible();
    });

    test("shows version traceability point", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Full version traceability")).toBeVisible();
    });

    test("shows human oversight point", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Human oversight accountability")).toBeVisible();
    });

    test("shows role-based access point", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await expect(page.getByText("Role-based access control")).toBeVisible();
    });

    test("shows encryption at rest point", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      // Use strong element selector since talking points use <strong> tags
      await expect(page.locator("strong").filter({ hasText: "Encryption at rest" })).toBeVisible();
      // AES-256-GCM appears in both sub-items and talking points, so just check one exists
      await expect(page.getByText(/AES-256-GCM/i).first()).toBeVisible();
    });
  });

  test.describe("Navigation", () => {
    test("navigates back to overview", async ({ page }) => {
      const controls = new ComplianceControlsPage(page);
      await controls.goto();

      await controls.navigateBack();
      await expect(page).toHaveURL(/\/compliance$/);
    });
  });
});
