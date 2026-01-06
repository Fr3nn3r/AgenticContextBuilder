import { test, expect } from "@playwright/test";
import { ClaimReviewPage } from "../pages/claim-review.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Claim Review", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("should display 3-column layout", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // All three sections should be visible
    await expect(review.docList).toBeVisible();
    await expect(review.documentViewer).toBeVisible();
    await expect(review.fieldsPanel).toBeVisible();
  });

  test("should display back button", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    await expect(review.backButton).toBeVisible();
  });

  test("should have document tabs visible", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Text tab should always be available
    await expect(review.textTab).toBeVisible();
  });

  test("should switch between document tabs", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Click text tab
    await review.switchToTab("text");
    await expect(review.textTab).toBeVisible();

    // JSON tab should be available for docs with extraction
    if (await review.jsonTab.isVisible()) {
      await review.switchToTab("json");
    }
  });

  test("should navigate back to claims list", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    await review.goBackToClaims();

    await expect(page).toHaveURL(/\/claims$/);
  });

  test("should display save button", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Look for the specific "Save Labels" button in the review panel
    await expect(page.getByRole("button", { name: "Save Labels" })).toBeVisible();
  });

  test("should display extracted fields", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Should show extracted fields from fixture - look for field names (use first() since multiple matches exist)
    await expect(page.getByText("Date Of Loss", { exact: true })).toBeVisible();
  });
});
