import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class ClaimsTablePage extends BasePage {
  readonly table: Locator;
  readonly searchInput: Locator;
  readonly claimRows: Locator;
  readonly gateStatusFilter: Locator;
  readonly batchSelector: Locator;

  constructor(page: Page) {
    super(page);
    this.table = page.locator("table");
    this.searchInput = page.getByPlaceholder(/search/i);
    this.claimRows = page.locator("tbody tr");
    this.gateStatusFilter = page.locator("select").first();
    this.batchSelector = page.getByTestId("batch-context-selector");
  }

  async goto() {
    // Navigate to batches first, then use tab to go to claims
    await this.page.goto("/batches");
    await this.waitForLoad();
    // Click the claims tab
    await this.page.getByTestId("batch-tab-claims").click();
    await this.waitForLoad();
  }

  async gotoWithBatch(batchId: string) {
    await this.page.goto(`/batches/${batchId}/claims`);
    await this.waitForLoad();
  }

  async gotoAllClaims() {
    await this.page.goto("/claims/all");
    await this.waitForLoad();
  }

  async expandClaim(claimId: string) {
    const row = this.page.locator("tr").filter({ hasText: claimId }).first();
    await row.click();
    // Wait for the expanded content
    await this.page.waitForTimeout(300);
  }

  async getClaimCount(): Promise<number> {
    // Count only the main claim rows, not expanded content
    const rows = this.page.locator("tbody > tr");
    return await rows.count();
  }

  async clickDocument(filename: string) {
    const docButton = this.page.getByRole("button", { name: new RegExp(filename, "i") });
    await docButton.click();
  }

  async searchClaims(query: string) {
    await this.searchInput.fill(query);
  }

  async isDocumentPackVisible(): Promise<boolean> {
    const docPack = this.page.getByText("Document Pack");
    return await docPack.isVisible();
  }
}
