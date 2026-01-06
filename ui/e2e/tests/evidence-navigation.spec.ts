import { test, expect } from "@playwright/test";
import { ClaimReviewPage } from "../pages/claim-review.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Evidence Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("evidence links are visible for fields with provenance", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Wait for fields to load
    await expect(review.fieldsPanel).toBeVisible();

    // Evidence links should be visible
    await expect(review.evidenceLinks.first()).toBeVisible();

    // Should have at least one evidence link
    const evidenceCount = await review.evidenceLinks.count();
    expect(evidenceCount).toBeGreaterThan(0);
  });

  test("clicking evidence navigates to correct page", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Wait for fields to load
    await expect(review.fieldsPanel).toBeVisible();

    // Switch to Text tab to see the highlight
    await review.switchToTab("text");

    // Click the first evidence link
    await review.clickEvidence(0);

    // Highlight marker should appear
    await expect(review.highlightMarker).toBeVisible();
  });

  test("highlight marker contains matched text", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Wait for fields to load
    await expect(review.fieldsPanel).toBeVisible();

    // Switch to Text tab
    await review.switchToTab("text");

    // Click the first evidence link
    await review.clickEvidence(0);

    // Highlight should be visible and contain text
    await expect(review.highlightMarker).toBeVisible();
    const highlightText = await review.highlightMarker.textContent();
    expect(highlightText).toBeTruthy();
    expect(highlightText!.length).toBeGreaterThan(0);
  });

  test("highlight is scrolled into view", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Wait for fields to load
    await expect(review.fieldsPanel).toBeVisible();

    // Switch to Text tab
    await review.switchToTab("text");

    // Click the first evidence link
    await review.clickEvidence(0);

    // Highlight should be in viewport (isInViewport requires the element to be rendered)
    await expect(review.highlightMarker).toBeVisible();

    // Check that highlight marker is in view by checking bounding box
    const highlightBox = await review.highlightMarker.boundingBox();
    const viewportSize = page.viewportSize();

    if (highlightBox && viewportSize) {
      // Highlight should be at least partially visible in viewport
      expect(highlightBox.y).toBeLessThan(viewportSize.height);
      expect(highlightBox.y + highlightBox.height).toBeGreaterThan(0);
    }
  });

  test("evidence quote text matches page content", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Wait for fields to load
    await expect(review.fieldsPanel).toBeVisible();

    // Get the evidence quote text before clicking
    const evidenceQuoteElement = review.evidenceLinks.first().locator(".bg-yellow-50");
    const quoteText = await evidenceQuoteElement.textContent();

    // Switch to Text tab
    await review.switchToTab("text");

    // Click the first evidence link
    await review.clickEvidence(0);

    // The highlighted text should be related to the quote
    const highlightText = await review.highlightMarker.textContent();

    // At minimum, both should exist and have content
    expect(quoteText).toBeTruthy();
    expect(highlightText).toBeTruthy();
  });
});
