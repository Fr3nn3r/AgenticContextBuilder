/**
 * Full Integration Flow E2E Test
 *
 * Tests the complete user journey: login -> upload -> pipeline -> review -> label
 *
 * This test only runs against real backends (local or remote).
 * Use E2E_TARGET=local or E2E_TARGET=remote to enable.
 *
 * Usage:
 *   # Against local servers (you start them first)
 *   E2E_TARGET=local npm run test:e2e integration-flow
 *
 *   # Against remote dev server
 *   E2E_TARGET=remote E2E_REMOTE_URL=https://dev.example.com E2E_USER=admin E2E_PASS=xxx npm run test:e2e integration-flow
 */

import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";
import { fileURLToPath } from "url";
import { getTarget, isRealBackend } from "../config/targets";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Get target configuration
const target = getTarget();
const shouldRun = isRealBackend();

// Credentials from target config
const credentials = target.credentials || { user: "", pass: "" };
const workspaceName = target.workspaceName;

const dataDir = path.resolve(__dirname, "..", "..", "..", "data", "05-FBR");
const uploadFiles = [
  "Claim_Report.pdf",
  "VAM Police.pdf",
  "WhatsApp Image 2026-01-05 at 11.34.25.jpeg",
  "WhatsApp Image 2026-01-14 at 20.50.00.jpeg",
];

function getUploadPaths(): string[] {
  const paths = uploadFiles.map((name) => path.join(dataDir, name));
  const missing = paths.filter((filePath) => !fs.existsSync(filePath));
  if (missing.length > 0) {
    throw new Error(`Missing upload fixtures: ${missing.join(", ")}`);
  }
  return paths;
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(credentials.user);
  await page.getByLabel("Password").fill(credentials.pass);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function ensureWorkspaceActive(page: Page) {
  await page.goto("/admin");
  await page.getByRole("button", { name: /workspaces/i }).click();

  const workspaceRow = page.locator("tr").filter({ hasText: workspaceName }).first();
  await expect(workspaceRow).toBeVisible();

  const activeBadgeCount = await workspaceRow.getByText("Active", { exact: true }).count();
  if (activeBadgeCount > 0) {
    return false;
  }

  await workspaceRow.getByRole("button", { name: "Activate" }).click();
  page.once("dialog", async (dialog) => {
    await dialog.accept();
  });
  await workspaceRow.getByRole("button", { name: "Confirm" }).click();
  await page.waitForURL(/\/login/);
  return true;
}

async function createNewClaimAndUpload(page: Page) {
  await page.goto("/claims/new");
  await expect(page.getByRole("heading", { name: "New Claim" })).toBeVisible();

  await page.getByRole("button", { name: /Add New Claim File/i }).click();

  const fileInputs = page.locator('input[type="file"]');
  const inputCount = await fileInputs.count();
  const fileInput = fileInputs.nth(inputCount - 1);
  await fileInput.setInputFiles(getUploadPaths());

  for (const fileName of uploadFiles) {
    await expect(page.getByText(fileName)).toBeVisible();
  }

  const claimIdElement = page.getByTestId("generated-claim-id").last();
  await expect(claimIdElement).toBeVisible();
  const claimId = await claimIdElement.textContent();
  if (!claimId) {
    throw new Error("Unable to find generated claim id");
  }

  return claimId;
}

async function runPipeline(page: Page) {
  const runButton = page.getByRole("button", { name: /Run Pipeline/i });
  await expect(runButton).toBeEnabled();
  await runButton.click();

  await expect(page.getByText("Overall Progress")).toBeVisible({ timeout: 120000 });
  await expect(page.getByRole("link", { name: /View in Claims Review/i })).toBeVisible({ timeout: 12 * 60 * 1000 });

  const batchText = await page.getByText(/Batch:/).first().textContent();
  const runId = batchText?.replace("Batch:", "").trim();
  if (!runId) {
    throw new Error(`Unable to parse run id from batch label: ${batchText ?? "(empty)"}`);
  }

  return runId;
}

async function selectBatch(page: Page, runId: string) {
  await page.goto("/batches");
  const selector = page.getByTestId("batch-context-selector");
  await expect(selector).toBeVisible();
  await expect(selector.locator(`option[value="${runId}"]`)).toHaveCount(1, { timeout: 120000 });
  await selector.selectOption(runId);
  await expect(selector).toHaveValue(runId);
}

async function labelFirstField(page: Page) {
  await page.getByTestId("batch-tab-documents").click();
  await expect(page.getByTestId("document-list")).toBeVisible({ timeout: 120000 });

  const docList = page.getByTestId("document-list");
  const firstDoc = docList.getByTestId("doc-list-item").first();
  await expect(firstDoc).toBeVisible({ timeout: 120000 });
  await firstDoc.click();

  // Wait for document to load fully
  await page.waitForLoadState("networkidle");

  // Find a field row that has the Confirm button (unlabeled field)
  // Fields with amber/warning border are unlabeled
  const fieldRows = page.getByTestId("field-row");
  const fieldCount = await fieldRows.count();

  let labeled = false;
  for (let i = 0; i < fieldCount; i++) {
    const fieldRow = fieldRows.nth(i);
    await fieldRow.click();

    // Check if Confirm button appears (means field is unlabeled)
    const confirmButton = page.getByRole("button", { name: /^Confirm$/i });
    const hasConfirm = await confirmButton.isVisible().catch(() => false);

    if (hasConfirm) {
      // Small delay to ensure DOM is stable
      await page.waitForTimeout(300);

      // Click Confirm
      await confirmButton.click({ force: true });

      // Wait for the label state to update
      await expect(page.getByText(/[1-9]\d* of \d+ labeled/)).toBeVisible({ timeout: 10000 });

      labeled = true;
      break;
    }

    // Collapse this field by clicking again before trying next
    await fieldRow.click();
  }

  if (!labeled) {
    // All fields already labeled - that's fine, just verify there's at least one labeled
    await expect(page.getByText(/[1-9]\d* of \d+ labeled/)).toBeVisible({ timeout: 10000 });
  }

  // Save if there are unsaved changes
  const saveButton = page.getByRole("button", { name: /^Save$/i });
  const saveEnabled = await saveButton.isEnabled().catch(() => false);
  if (saveEnabled) {
    await saveButton.click();
    await expect(saveButton).toBeDisabled({ timeout: 60000 });
  }

  // Verify document shows as labeled in the list
  await expect(docList.getByText("Labeled")).toBeVisible({ timeout: 60000 });
}

test.describe("Full Integration Flow", () => {
  test.describe.configure({ mode: "serial" });

  // Skip if running in mock mode - this test requires a real backend
  test.skip(!shouldRun, "Set E2E_TARGET=local or E2E_TARGET=remote to run against real backend.");
  test.skip(!credentials.user || !credentials.pass, "Credentials required: set E2E_USER and E2E_PASS.");

  test("login, activate workspace, upload docs, run pipeline, label, verify screens", async ({ page }) => {
    test.setTimeout(20 * 60 * 1000);
    page.setDefaultTimeout(60000);

    await login(page);

    const didActivate = await ensureWorkspaceActive(page);
    if (didActivate) {
      await login(page);
    }

    const claimId = await createNewClaimAndUpload(page);
    const runId = await runPipeline(page);

    await selectBatch(page, runId);

    await expect(page.getByTestId("phase-ingestion")).toBeVisible({ timeout: 120000 });

    await labelFirstField(page);

    await page.getByTestId("batch-tab-claims").click();
    await expect(page.getByText(claimId)).toBeVisible({ timeout: 120000 });

    await page.getByTestId("batch-tab-classification").click();
    // Wait for classification data to load - look for doc type distribution (use first match)
    await expect(page.getByText(/fnol|police|insurance|vehicle|damage/i).first()).toBeVisible({ timeout: 120000 });

    await page.getByTestId("batch-tab-metrics").click();
    await expect(page.getByTestId("kpi-row")).toBeVisible({ timeout: 120000 });

    await page.getByTestId("nav-templates").click();
    await expect(page.getByRole("heading", { name: "Extraction Templates" })).toBeVisible();

    await page.getByTestId("nav-pipeline").click();
    await expect(page.getByRole("heading", { name: "Pipeline Control Center" })).toBeVisible();

    await page.getByTestId("nav-truth").click();
    await expect(page.getByRole("heading", { name: "Ground Truth" }).first()).toBeVisible();

    await page.getByPlaceholder("Claim ID").fill(claimId);

    const runSelect = page.getByTestId("truth-run-filter");
    await runSelect.selectOption(runId);

    const stateSelect = page.getByTestId("truth-state-filter");
    await stateSelect.selectOption("LABELED");

    await expect(page.getByText("No truth entries found.")).not.toBeVisible({ timeout: 120000 });
  });
});
