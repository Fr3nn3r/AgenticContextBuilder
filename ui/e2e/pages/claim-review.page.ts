import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class ClaimReviewPage extends BasePage {
  readonly docList: Locator;
  readonly documentViewer: Locator;
  readonly fieldsPanel: Locator;
  readonly backButton: Locator;
  readonly textTab: Locator;
  readonly pdfTab: Locator;
  readonly jsonTab: Locator;
  readonly saveButton: Locator;
  readonly docCounter: Locator;
  readonly nextDocButton: Locator;
  readonly prevDocButton: Locator;
  // New locators for tests
  readonly prevClaimButton: Locator;
  readonly nextClaimButton: Locator;
  readonly docStripItems: Locator;
  readonly evidenceLinks: Locator;
  readonly highlightMarker: Locator;

  constructor(page: Page) {
    super(page);
    // Left panel - document list
    this.docList = page.locator(".border-r").first();
    // Center panel - document viewer
    this.documentViewer = page.locator('[class*="flex-1"]').first();
    // Right panel - fields
    this.fieldsPanel = page.locator(".border-l").first();
    // Navigation
    this.backButton = page.getByRole("button", { name: /back|claims/i });
    // Tabs
    this.textTab = page.getByRole("button", { name: "Text" });
    this.pdfTab = page.getByRole("button", { name: "PDF" });
    this.jsonTab = page.getByRole("button", { name: "JSON" });
    // Save - use testid for stability
    this.saveButton = page.getByTestId("save-labels-btn");
    // Doc navigation - look for the format "1/3" or similar
    this.docCounter = page.locator('text=/\\d+\\/\\d+/');
    this.nextDocButton = page.locator('button:has(svg[class*="lucide-chevron-right"])').last();
    this.prevDocButton = page.locator('button:has(svg[class*="lucide-chevron-left"])').last();
    // Claim navigation
    this.prevClaimButton = page.getByTestId("prev-claim");
    this.nextClaimButton = page.getByTestId("next-claim");
    // Doc strip
    this.docStripItems = page.getByTestId("doc-strip-item");
    // Evidence
    this.evidenceLinks = page.getByTestId("evidence-link");
    this.highlightMarker = page.getByTestId("highlight-marker");
  }

  async goto(claimId: string, docId?: string) {
    const url = docId
      ? `/claims/${claimId}/review?doc=${docId}`
      : `/claims/${claimId}/review`;
    await this.page.goto(url);
    await this.waitForLoad();
  }

  async switchToTab(tab: "text" | "pdf" | "json") {
    const tabMap = {
      text: this.textTab,
      pdf: this.pdfTab,
      json: this.jsonTab,
    };
    await tabMap[tab].click();
  }

  async navigateToNextDoc() {
    await this.nextDocButton.click();
    await this.page.waitForTimeout(300);
  }

  async navigateToPrevDoc() {
    await this.prevDocButton.click();
    await this.page.waitForTimeout(300);
  }

  async goBackToClaims() {
    await this.backButton.click();
    await this.page.waitForURL("**/claims");
  }

  async getDocCounterText(): Promise<string> {
    return (await this.docCounter.textContent()) ?? "";
  }

  async selectDocumentFromList(docType: string) {
    const docItem = this.docList.getByText(new RegExp(docType, "i")).first();
    await docItem.click();
    await this.page.waitForTimeout(300);
  }

  async clickEvidence(index: number = 0) {
    await this.evidenceLinks.nth(index).click();
    await this.page.waitForTimeout(500);
  }

  async isHighlightVisible(): Promise<boolean> {
    return await this.highlightMarker.isVisible();
  }

  async navigateToPrevClaim() {
    await this.prevClaimButton.click();
    await this.waitForLoad();
  }

  async navigateToNextClaim() {
    await this.nextClaimButton.click();
    await this.waitForLoad();
  }

  async getDocStripItemCount(): Promise<number> {
    return await this.docStripItems.count();
  }
}
