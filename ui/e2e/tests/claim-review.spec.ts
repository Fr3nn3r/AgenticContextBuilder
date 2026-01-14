import { test, expect } from "@playwright/test";
import { ClaimReviewPage } from "../pages/claim-review.page";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Claim Review", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
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

  test("prev/next claim controls exist", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // Prev/Next claim buttons should exist
    await expect(review.prevClaimButton).toBeVisible();
    await expect(review.nextClaimButton).toBeVisible();
  });

  test("prev claim button is disabled for first claim", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // First claim in fixture has prev_claim_id: null, so prev should be disabled
    await expect(review.prevClaimButton).toBeDisabled();
  });

  test("next claim button navigates to next claim", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // Next claim should be enabled (fixture has next_claim_id: "CLM-2024-002")
    await expect(review.nextClaimButton).not.toBeDisabled();

    // Click next claim
    await review.nextClaimButton.click();

    // URL should change to next claim
    await expect(page).toHaveURL(/CLM-2024-002/);
  });

  test("doc strip shows document list with type and status", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // Doc strip items should be visible
    await expect(review.docStripItems.first()).toBeVisible();

    // Should have 3 docs (from fixture)
    const docCount = await review.getDocStripItemCount();
    expect(docCount).toBe(3);

    // Check first doc shows doc_type
    const firstDoc = review.docStripItems.first();
    await expect(firstDoc).toContainText("loss_notice");
  });

  test("doc strip shows labeled status indicator", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // From fixture: doc_002 (police_report) has has_labels: true
    // Look for the checkmark SVG that indicates labeled status
    const docWithLabels = review.docStripItems.filter({
      hasText: "police_report",
    });
    await expect(docWithLabels).toBeVisible();

    // The labeled doc should have a checkmark (theme-aware class)
    const checkmark = docWithLabels.locator("svg.text-success");
    await expect(checkmark).toBeVisible();
  });

  test("doc strip shows quality gate indicator", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001");

    // Each doc should have a gate status dot
    // From fixture: doc_001 = pass (green), doc_002 = warn (yellow), doc_003 = fail (red)

    // Check for colored dots in each doc strip item
    const firstDoc = review.docStripItems.first();
    const gateDot = firstDoc.locator(".rounded-full").first();
    await expect(gateDot).toBeVisible();
  });

  test("clicking doc in strip updates viewer", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Click on police_report doc
    await review.selectDocumentFromList("police_report");

    // URL should update to include new doc
    await expect(page).toHaveURL(/doc=doc_002/);
  });
});
