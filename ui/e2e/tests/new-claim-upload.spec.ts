import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const fixturesDir = path.join(__dirname, "..", "fixtures");
const pendingClaimsFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "pending-claims.json"), "utf-8")
);

test.describe("New Claim Upload", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");

    // Override pending claims to return empty on first load, then populated after upload.
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
  });

  test("uploads documents and starts pipeline", async ({ page }) => {
    await page.goto("/claims/new");

    await expect(page.getByRole("heading", { name: "New Claim" })).toBeVisible();

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "loss_notice.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    await expect(page.getByText("loss_notice.pdf")).toBeVisible();

    const runButton = page.getByRole("button", { name: /Run Pipeline/i });
    await expect(runButton).toBeEnabled();
    await runButton.click();

    await expect(page.getByText("Overall Progress")).toBeVisible();
    await expect(page.getByText(/Batch:/)).toBeVisible();
  });

  test("shows View in Batches button on completion and navigates to batch documents", async ({ page }) => {
    // Mock WebSocket to immediately send batch_complete after connection
    await page.addInitScript(() => {
      const OriginalWebSocket = window.WebSocket;
      (window as unknown as { WebSocket: typeof WebSocket }).WebSocket = class extends OriginalWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          super(url, protocols);
          // Send batch_complete event shortly after connection
          this.addEventListener("open", () => {
            setTimeout(() => {
              const completeEvent = new MessageEvent("message", {
                data: JSON.stringify({
                  type: "batch_complete",
                  summary: { total: 1, success: 1, failed: 0 },
                }),
              });
              this.dispatchEvent(completeEvent);
            }, 100);
          });
        }
      };
    });

    await page.goto("/claims/new");

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "test_doc.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    const runButton = page.getByRole("button", { name: /Run Pipeline/i });
    await runButton.click();

    // Wait for completion state - "View in Batches" button should appear
    const viewButton = page.getByRole("link", { name: "View in Batches" });
    await expect(viewButton).toBeVisible({ timeout: 5000 });

    // Verify the href points to batch documents page (format: /batches/{batch_id}/documents)
    const href = await viewButton.getAttribute("href");
    expect(href).toMatch(/^\/batches\/[^/]+\/documents$/);

    // Click and verify navigation to batch documents page
    await viewButton.click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/documents$/);
  });
});
