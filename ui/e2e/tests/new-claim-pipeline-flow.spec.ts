/**
 * E2E test: Upload-to-Pipeline-to-Assessment flow on NewClaimPage.
 *
 * Simulates the full lifecycle via mocked API + WebSocket:
 *   Upload docs -> Start pipeline -> Ingest -> Classify -> Extract
 *   -> Assessment (reconcile -> enrich -> screen -> process -> decide)
 *   -> Completion with navigation links
 */

import { test, expect, Page } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const fixturesDir = path.join(__dirname, "..", "fixtures");
const pendingClaimsFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "pending-claims.json"), "utf-8"),
);

// Claim/doc IDs matching the pending-claims fixture
const CLAIM_ID = "CLM-2026-TEST-001";
const DOC_1 = "pend_doc_001";
const DOC_2 = "pend_doc_002";
const BATCH_ID = "run_2026_001";

// ---- helpers ----

/**
 * Inject a fake WebSocket that buffers `send()` calls so the test can
 * push server->client messages at controlled points.
 *
 * Returns a handle object stored on `window.__wsMock` that the test
 * can reach via `page.evaluate`.
 */
function buildWsMockScript(batchId: string) {
  // This runs inside the browser via addInitScript
  return `
    (() => {
      const RealWS = window.WebSocket;
      const handle = { messages: [], socket: null };
      window.__wsMock = handle;

      window.WebSocket = class FakeWebSocket extends EventTarget {
        static CONNECTING = 0;
        static OPEN = 1;
        static CLOSING = 2;
        static CLOSED = 3;
        CONNECTING = 0;
        OPEN = 1;
        CLOSING = 2;
        CLOSED = 3;

        readyState = 0; // CONNECTING
        url = "";
        protocol = "";
        bufferedAmount = 0;
        extensions = "";
        binaryType = "blob";

        // Required event handler properties
        onopen = null;
        onmessage = null;
        onerror = null;
        onclose = null;

        constructor(url, protocols) {
          super();
          this.url = url;
          handle.socket = this;

          // Simulate async open
          setTimeout(() => {
            this.readyState = 1; // OPEN
            const evt = new Event("open");
            if (this.onopen) this.onopen(evt);
            this.dispatchEvent(evt);
          }, 50);
        }

        send(data) {
          handle.messages.push(data);
        }

        close() {
          this.readyState = 3; // CLOSED
          const evt = new CloseEvent("close", { code: 1000, reason: "" });
          if (this.onclose) this.onclose(evt);
          this.dispatchEvent(evt);
        }
      };

      // Helper: push a server message into the fake socket
      handle.pushMessage = function(data) {
        const sock = handle.socket;
        if (!sock) return;
        const evt = new MessageEvent("message", { data: JSON.stringify(data) });
        if (sock.onmessage) sock.onmessage(evt);
        sock.dispatchEvent(evt);
      };
    })();
  `;
}

/** Push a WS message from the test into the fake socket. */
async function pushWsMessage(page: Page, data: Record<string, unknown>) {
  await page.evaluate((msg) => {
    (window as any).__wsMock?.pushMessage(msg);
  }, data);
}

/** Wait until the fake WebSocket is open. */
async function waitForWsOpen(page: Page) {
  await page.waitForFunction(() => {
    const mock = (window as any).__wsMock;
    return mock?.socket?.readyState === 1;
  }, null, { timeout: 5000 });
}

// ---- tests ----

test.describe("New Claim: Upload -> Pipeline -> Assessment flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");

    // Override pending-claims: empty on first call, populated after upload
    await page.unroute("**/api/upload/pending");
    let pendingCalls = 0;
    await page.route("**/api/upload/pending", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      pendingCalls += 1;
      const body = pendingCalls === 1 ? [] : pendingClaimsFixture;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    });

    // Install the fake WebSocket before page loads
    await page.addInitScript(buildWsMockScript(BATCH_ID));
  });

  test("full flow: upload, extraction progress, assessment progress, completion links", async ({
    page,
  }) => {
    // ---- 1. Navigate & upload ----
    await page.goto("/claims/new");
    await expect(
      page.getByRole("main").getByRole("heading", { name: "New Claim" }),
    ).toBeVisible();

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles([
      {
        name: "loss_notice.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.4 loss notice content"),
      },
      {
        name: "police_report.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.4 police report content"),
      },
    ]);

    // After upload the fixture shows 2 docs
    await expect(page.getByText("loss_notice.pdf")).toBeVisible();
    await expect(page.getByText("police_report.pdf")).toBeVisible();

    // ---- 2. Start pipeline ----
    const runButton = page.getByRole("button", { name: /Run Pipeline/i });
    await expect(runButton).toBeEnabled();
    await runButton.click();

    // Should show pipeline progress UI
    await expect(page.getByText("Running")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("run_2026_001")).toBeVisible();
    await expect(page.getByText("Processing documents...")).toBeVisible();

    // Wait for the fake WS to connect
    await waitForWsOpen(page);

    // ---- 3. Simulate extraction progress via WS ----

    // Doc 1: ingesting
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_1,
      phase: "ingesting",
    });
    // Doc 2: ingesting
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_2,
      phase: "ingesting",
    });

    // Doc 1: classifying
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_1,
      phase: "classifying",
    });

    // Doc 1: extracting
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_1,
      phase: "extracting",
    });

    // Doc 2: classifying -> extracting -> done
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_2,
      phase: "classifying",
    });
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_2,
      phase: "extracting",
    });
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_2,
      phase: "done",
    });

    // Doc 1: done
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_1,
      phase: "done",
    });

    // Batch extraction complete
    await pushWsMessage(page, {
      type: "batch_complete",
      summary: { total: 2, success: 2, failed: 0 },
    });

    // ---- 4. Simulate assessment phase via WS ----

    await pushWsMessage(page, {
      type: "assessment_starting",
      claim_ids: [CLAIM_ID],
    });

    // Should switch to assessment UI
    await expect(page.getByText("Assessing claims...")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Claim Assessment")).toBeVisible();

    // Reconciliation stage
    await pushWsMessage(page, {
      type: "assessment_stage",
      claim_id: CLAIM_ID,
      stage: "reconciliation",
      status: "running",
    });

    // Enrichment stage
    await pushWsMessage(page, {
      type: "assessment_stage",
      claim_id: CLAIM_ID,
      stage: "enrichment",
      status: "running",
    });

    // Screening stage
    await pushWsMessage(page, {
      type: "assessment_stage",
      claim_id: CLAIM_ID,
      stage: "screening",
      status: "running",
    });

    // Processing stage
    await pushWsMessage(page, {
      type: "assessment_stage",
      claim_id: CLAIM_ID,
      stage: "processing",
      status: "running",
    });

    // Decision stage
    await pushWsMessage(page, {
      type: "assessment_stage",
      claim_id: CLAIM_ID,
      stage: "decision",
      status: "running",
    });

    // Assessment complete for claim
    await pushWsMessage(page, {
      type: "assessment_complete",
      claim_id: CLAIM_ID,
      decision: "APPROVE",
      assessment_id: "ASM-run_2026_001-CLM-2026-TEST-001",
    });

    // Verify decision badge appears
    await expect(page.getByText("APPROVE")).toBeVisible({ timeout: 3000 });

    // All assessments complete
    await pushWsMessage(page, {
      type: "all_assessments_complete",
      results: [
        {
          claim_id: CLAIM_ID,
          decision: "APPROVE",
          assessment_id: "ASM-run_2026_001-CLM-2026-TEST-001",
        },
      ],
    });

    // ---- 5. Verify completion state ----

    await expect(page.getByText("Pipeline completed.")).toBeVisible({ timeout: 5000 });

    // "View in Batches" link
    const viewBatchesLink = page.getByRole("link", { name: "View in Batches" });
    await expect(viewBatchesLink).toBeVisible();
    const batchHref = await viewBatchesLink.getAttribute("href");
    expect(batchHref).toMatch(/^\/batches\/[^/]+\/documents$/);

    // "Upload More Claims" button
    await expect(
      page.getByRole("button", { name: "Upload More Claims" }),
    ).toBeVisible();

    // Per-claim assessment link
    const assessLink = page.getByRole("link", {
      name: new RegExp(`View ${CLAIM_ID} Assessment`),
    });
    await expect(assessLink).toBeVisible();
    const assessHref = await assessLink.getAttribute("href");
    expect(assessHref).toBe(`/claims/${CLAIM_ID}`);
  });

  test("handles extraction failure for one doc (partial) then assessment", async ({
    page,
  }) => {
    await page.goto("/claims/new");

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "loss_notice.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    const runButton = page.getByRole("button", { name: /Run Pipeline/i });
    await runButton.click();

    await waitForWsOpen(page);

    // Doc 1 succeeds
    await pushWsMessage(page, { type: "doc_progress", doc_id: DOC_1, phase: "done" });
    // Doc 2 fails at extracting
    await pushWsMessage(page, {
      type: "doc_progress",
      doc_id: DOC_2,
      phase: "failed",
      error: "Extraction timeout",
      failed_at_stage: "extracting",
    });

    // Batch completes with mixed results
    await pushWsMessage(page, {
      type: "batch_complete",
      summary: { total: 2, success: 1, failed: 1 },
    });

    // Assessment starts for the successful claim
    await pushWsMessage(page, {
      type: "assessment_starting",
      claim_ids: [CLAIM_ID],
    });

    await expect(page.getByText("Claim Assessment")).toBeVisible({ timeout: 5000 });

    // Assessment error
    await pushWsMessage(page, {
      type: "assessment_error",
      claim_id: CLAIM_ID,
      error: "Insufficient data for assessment",
    });

    // All assessments complete (with errors)
    await pushWsMessage(page, {
      type: "all_assessments_complete",
      results: [],
    });

    // Should reach completion state
    await expect(page.getByText("Pipeline completed.")).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("link", { name: "View in Batches" })).toBeVisible();

    // No assessment link when assessment errored (phase != 'complete')
    await expect(
      page.getByRole("link", { name: new RegExp(`View ${CLAIM_ID} Assessment`) }),
    ).not.toBeVisible();
  });

  test("cancel during extraction shows cancelled state", async ({ page }) => {
    await page.goto("/claims/new");

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "loss_notice.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    const runButton = page.getByRole("button", { name: /Run Pipeline/i });
    await runButton.click();

    await waitForWsOpen(page);

    // Simulate some progress
    await pushWsMessage(page, { type: "doc_progress", doc_id: DOC_1, phase: "ingesting" });

    // User clicks Cancel
    const cancelButton = page.getByRole("button", { name: /Cancel/i });
    await cancelButton.click();

    // Confirmation modal appears
    await expect(page.getByText("Cancel Pipeline?")).toBeVisible();
    await expect(
      page.getByText("Documents that have already been processed will be saved."),
    ).toBeVisible();

    // Confirm cancellation
    await page.getByRole("button", { name: "Cancel Pipeline" }).click();

    // Server responds with cancelled
    await pushWsMessage(page, { type: "batch_cancelled" });

    // Should reach completion with cancelled status
    await expect(page.getByText("Pipeline completed.")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Cancelled")).toBeVisible();
  });

  test("reset after completion returns to upload state", async ({ page }) => {
    await page.goto("/claims/new");

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "loss_notice.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    const runButton = page.getByRole("button", { name: /Run Pipeline/i });
    await runButton.click();

    await waitForWsOpen(page);

    // Fast-forward to completion (no assessment)
    await pushWsMessage(page, { type: "doc_progress", doc_id: DOC_1, phase: "done" });
    await pushWsMessage(page, { type: "doc_progress", doc_id: DOC_2, phase: "done" });
    await pushWsMessage(page, {
      type: "batch_complete",
      summary: { total: 2, success: 2, failed: 0 },
    });

    await expect(page.getByText("Pipeline completed.")).toBeVisible({ timeout: 5000 });

    // Click "Upload More Claims"
    await page.getByRole("button", { name: "Upload More Claims" }).click();

    // Should be back in upload state
    await expect(
      page.getByText("Upload documents and run the extraction pipeline."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Add New Claim File/i }),
    ).toBeVisible();
  });

  test("delete claim (trash icon) removes locally-created claim without documents", async ({
    page,
  }) => {
    // Override the pending route to always return empty (no server-side claims)
    await page.unroute("**/api/upload/pending");
    await page.route("**/api/upload/pending", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "[]",
        });
      } else {
        await route.continue();
      }
    });

    // Override DELETE to return 404 (claim doesn't exist on server)
    await page.unroute(/\/api\/upload\/claim\/[^/]+$/);
    await page.route(/\/api\/upload\/claim\/[^/]+$/, async (route) => {
      if (route.request().method() === "DELETE") {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Pending claim not found" }),
        });
        return;
      }
      // POST (upload) still returns success for other test parts
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ claim_id: "test", documents: [] }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/claims/new");

    // Auto-created local claim should be visible (generated ID like CLM-XXXXXXXX-XXXX)
    const claimIdEl = page.locator('[data-testid="generated-claim-id"]');
    await expect(claimIdEl).toBeVisible();
    const claimId = await claimIdEl.textContent();

    // Click the trash icon (the "Remove claim" button)
    const trashButton = page.getByTitle("Remove claim");
    await expect(trashButton).toBeVisible();
    await trashButton.click();

    // Claim should disappear from the UI even though the server returned 404
    await expect(claimIdEl).not.toBeVisible({ timeout: 3000 });

    // The "No claim files yet" message or auto-created new claim should appear
    // (page shows empty state or auto-creates a new one)
    // At minimum the original claim ID should be gone
    if (claimId) {
      await expect(page.getByText(claimId)).not.toBeVisible();
    }
  });
});
