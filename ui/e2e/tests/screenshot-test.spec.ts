import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";
import * as path from "path";
import * as fs from "fs";

/**
 * Screenshot Functionality Tests for Agent Workflows
 *
 * Purpose: Capture screenshots of specific pages for AI agent analysis.
 *
 * Usage:
 *   npm run test:e2e:screenshot                    # Run all screenshot tests
 *   npx playwright test screenshot-test -g "batches"  # Capture specific page
 *
 * Output: Screenshots saved to ui/test-screenshots/
 */

const SCREENSHOT_DIR = path.join(process.cwd(), "test-screenshots");

// Ensure screenshot directory exists
test.beforeAll(async () => {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
});

test.describe("Screenshot Capture", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("batches overview", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("batch-context-bar")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "batches-overview.png"),
      fullPage: false,
    });
  });

  test("batches documents tab", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-documents").click();
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "batches-documents.png"),
      fullPage: false,
    });
  });

  test("batches classification tab", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-classification").click();
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "batches-classification.png"),
      fullPage: false,
    });
  });

  test("all claims page", async ({ page }) => {
    await page.goto("/claims/all");
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "all-claims.png"),
      fullPage: false,
    });
  });

  test("templates page", async ({ page }) => {
    await page.goto("/templates");
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "templates.png"),
      fullPage: false,
    });
  });

  test("pipeline page", async ({ page }) => {
    await page.goto("/pipeline");
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "pipeline.png"),
      fullPage: false,
    });
  });

  test("compliance page", async ({ page }) => {
    await page.goto("/compliance");
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "compliance.png"),
      fullPage: false,
    });
  });

  test("admin page", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "admin.png"),
      fullPage: false,
    });
  });
});
