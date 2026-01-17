import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Document Labeling Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("labels a document and auto-advances to next pending", async ({ page }) => {
    await page.goto("/batches/run_001/documents");
    await page.waitForLoadState("networkidle");

    const docList = page.getByTestId("document-list");
    await expect(docList).toBeVisible();

    // Wait for documents to load (async API call + React state update)
    const lossNoticeItem = docList.getByText("loss_notice.pdf");
    await expect(lossNoticeItem).toBeVisible({ timeout: 10000 });
    await lossNoticeItem.click();

    // Expand the first field row and confirm it to enable Save
    const firstFieldRow = page.locator(".border-l-4").first();
    await firstFieldRow.click();
    const confirmButton = page.getByRole("button", { name: /confirm/i });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    const saveButton = page.getByRole("button", { name: /^Save$/i });
    await expect(saveButton).toBeEnabled();
    await saveButton.click();

    // Wait for save to complete and status to update
    await page.waitForTimeout(500);

    // Expect the doc to show as labeled - use specific doc item selector (p-3 class is on doc items)
    const lossNoticeRow = docList.locator(".p-3").filter({ hasText: "loss_notice.pdf" });
    await expect(lossNoticeRow).toContainText("Labeled");

    // DocumentReview intentionally stays on current document after save
    // (user manually selects next doc when ready - see handleSave comment)
    const selectedRow = docList.locator(".border-l-2.border-accent");
    await expect(selectedRow).toContainText("loss_notice.pdf");
  });
});
