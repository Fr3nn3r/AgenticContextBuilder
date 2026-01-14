import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Document Labeling Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("labels a document and auto-advances to next pending", async ({ page }) => {
    await page.goto("/batches/run_001/documents");
    await page.waitForLoadState("networkidle");

    const docList = page.locator(".w-72.border-r");
    await expect(docList).toBeVisible();

    const lossNoticeItem = docList.getByText("loss_notice.pdf");
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

    // Expect the doc to show as labeled
    const labeledRow = docList.locator("div").filter({ hasText: "loss_notice.pdf" });
    await expect(labeledRow).toContainText("Labeled");

    // Auto-advance should select the next pending document
    const selectedRow = docList.locator(".bg-accent\\/10.border-l-2.border-accent");
    await expect(selectedRow).toContainText("insurance_policy.pdf");
  });
});
