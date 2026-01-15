/**
 * Page Objects for Compliance UI Screens
 *
 * Following the Page Object Model pattern used throughout the e2e tests.
 * Each compliance screen gets its own class with locators and helper methods.
 */

import { Page, Locator, expect } from "@playwright/test";
import { config } from "../config/test-config";

/**
 * Compliance Overview (Dashboard) Page
 * Route: /compliance
 */
export class ComplianceOverviewPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly hashChainCard: Locator;
  readonly hashChainStatusValid: Locator;
  readonly hashChainStatusInvalid: Locator;
  readonly recordCountValue: Locator;
  readonly decisionsCard: Locator;
  readonly bundlesCard: Locator;
  readonly recentDecisionsList: Locator;
  readonly verificationQuickLink: Locator;
  readonly bundlesQuickLink: Locator;
  readonly controlsQuickLink: Locator;
  readonly ledgerLink: Locator;
  readonly loadingIndicator: Locator;
  readonly errorMessage: Locator;
  readonly emptyDecisionsMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole("heading", { name: "Compliance Dashboard" });
    this.hashChainCard = page.locator(".bg-card").filter({ hasText: "Hash Chain Integrity" });
    this.hashChainStatusValid = page.getByText("Valid").first();
    this.hashChainStatusInvalid = page.getByText("Invalid").first();
    // Record count appears near "records" text - look within the hash chain card
    this.recordCountValue = this.hashChainCard.locator("text=/\\d+/").first();
    this.decisionsCard = page.locator(".bg-card").filter({ hasText: "Decision Records" });
    this.bundlesCard = page.locator(".bg-card").filter({ hasText: "Version Bundles" });
    this.recentDecisionsList = page.locator("text=Recent Decisions").locator("..").locator("..");
    this.verificationQuickLink = page.getByRole("link", { name: /verification center/i });
    this.bundlesQuickLink = page.getByRole("link", { name: /version bundles/i }).first();
    this.controlsQuickLink = page.getByRole("link", { name: /control mapping/i });
    this.ledgerLink = page.getByRole("link", { name: /browse ledger/i });
    this.loadingIndicator = page.getByText("Loading compliance overview...");
    this.errorMessage = page.locator("[class*='destructive']");
    this.emptyDecisionsMessage = page.getByText("No decisions recorded yet");
  }

  async goto(): Promise<void> {
    await this.page.goto("/compliance");
    await this.page.waitForLoadState("networkidle");
  }

  async expectLoaded(): Promise<void> {
    await expect(this.heading).toBeVisible({ timeout: config.timeout.navigation });
  }

  async expectValidHashChain(): Promise<void> {
    await expect(this.hashChainStatusValid).toBeVisible();
  }

  async expectInvalidHashChain(): Promise<void> {
    await expect(this.hashChainStatusInvalid).toBeVisible();
  }

  async getRecordCount(): Promise<number> {
    const text = await this.recordCountValue.textContent();
    return parseInt(text || "0");
  }

  async navigateToVerification(): Promise<void> {
    await this.verificationQuickLink.click();
    await this.page.waitForURL(/\/compliance\/verification/);
  }

  async navigateToLedger(): Promise<void> {
    await this.ledgerLink.click();
    await this.page.waitForURL(/\/compliance\/ledger/);
  }

  async navigateToBundles(): Promise<void> {
    await this.bundlesQuickLink.click();
    await this.page.waitForURL(/\/compliance\/version-bundles/);
  }

  async navigateToControls(): Promise<void> {
    await this.controlsQuickLink.click();
    await this.page.waitForURL(/\/compliance\/controls/);
  }
}

/**
 * Compliance Ledger (Decision List) Page
 * Route: /compliance/ledger
 */
export class ComplianceLedgerPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly typeFilter: Locator;
  readonly claimFilter: Locator;
  readonly docFilter: Locator;
  readonly resultsTable: Locator;
  readonly tableRows: Locator;
  readonly emptyState: Locator;
  readonly loadingIndicator: Locator;
  readonly errorMessage: Locator;
  readonly resultCount: Locator;
  readonly backLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole("heading", { name: "Decision Ledger" });
    // Use more specific selector - the filter select is in main content area, not sidebar
    // Look for select that contains "All Types" option
    this.typeFilter = page.locator("main select").first();
    this.claimFilter = page.getByPlaceholder("Filter by claim...");
    this.docFilter = page.getByPlaceholder("Filter by doc...");
    this.resultsTable = page.locator("table");
    this.tableRows = page.locator("tbody tr");
    this.emptyState = page.getByText("No decisions found matching filters");
    this.loadingIndicator = page.getByText("Loading decisions...");
    this.errorMessage = page.locator(".bg-destructive\\/10");
    this.resultCount = page.locator("text=/Showing \\d+ decision/i");
    this.backLink = page.getByRole("link", { name: /back to overview/i });
  }

  async goto(): Promise<void> {
    await this.page.goto("/compliance/ledger");
    await this.page.waitForLoadState("networkidle");
  }

  async gotoWithFilters(params: {
    type?: string;
    claim?: string;
    doc?: string;
  }): Promise<void> {
    const searchParams = new URLSearchParams();
    if (params.type) searchParams.set("type", params.type);
    if (params.claim) searchParams.set("claim", params.claim);
    if (params.doc) searchParams.set("doc", params.doc);
    const query = searchParams.toString();
    await this.page.goto(`/compliance/ledger${query ? `?${query}` : ""}`);
    await this.page.waitForLoadState("networkidle");
  }

  async expectLoaded(): Promise<void> {
    await expect(this.heading).toBeVisible({ timeout: config.timeout.navigation });
  }

  async filterByType(type: string): Promise<void> {
    await this.typeFilter.selectOption(type);
    await this.page.waitForLoadState("networkidle");
  }

  async filterByClaim(claim: string): Promise<void> {
    await this.claimFilter.fill(claim);
    await this.page.waitForLoadState("networkidle");
  }

  async filterByDoc(doc: string): Promise<void> {
    await this.docFilter.fill(doc);
    await this.page.waitForLoadState("networkidle");
  }

  async clearFilters(): Promise<void> {
    await this.typeFilter.selectOption("");
    await this.claimFilter.clear();
    await this.docFilter.clear();
    await this.page.waitForLoadState("networkidle");
  }

  async getRowCount(): Promise<number> {
    return await this.tableRows.count();
  }

  async expectResultCount(count: number): Promise<void> {
    await expect(this.resultCount).toContainText(`${count} decision`);
  }

  async navigateBack(): Promise<void> {
    await this.backLink.click();
    await this.page.waitForURL(/\/compliance$/);
  }
}

/**
 * Compliance Verification Page
 * Route: /compliance/verification
 */
export class ComplianceVerificationPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly statusIconValid: Locator;
  readonly statusIconInvalid: Locator;
  readonly statusTextValid: Locator;
  readonly statusTextInvalid: Locator;
  readonly totalRecordsLabel: Locator;
  readonly totalRecordsValue: Locator;
  readonly lastVerifiedLabel: Locator;
  readonly lastVerifiedValue: Locator;
  readonly breakLocationSection: Locator;
  readonly breakLocationValue: Locator;
  readonly breakReason: Locator;
  readonly reVerifyButton: Locator;
  readonly loadingSpinner: Locator;
  readonly explanationSection: Locator;
  readonly securityNote: Locator;
  readonly backLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole("heading", { name: "Verification Center" });
    this.statusIconValid = page.locator("[class*='bg-green']").first();
    this.statusIconInvalid = page.locator("[class*='bg-red']").first();
    this.statusTextValid = page.getByText("Hash Chain Valid");
    this.statusTextInvalid = page.getByText("Hash Chain Invalid");
    this.totalRecordsLabel = page.getByText("Total Records");
    // The count is in a dd element after the "Total Records" dt
    this.totalRecordsValue = page.locator("dt:has-text('Total Records') + dd");
    this.lastVerifiedLabel = page.getByText("Last Verified");
    this.lastVerifiedValue = page.locator("dt:has-text('Last Verified') + dd");
    // Chain break section - look for any element with red background containing break info
    this.breakLocationSection = page.locator("[class*='red']").filter({ hasText: /break|chain/i });
    this.breakLocationValue = page.getByText(/Record #\d+/);
    this.breakReason = page.getByText(/hash mismatch/i);
    // Button can be in various states
    this.reVerifyButton = page.getByRole("button", { name: /re-run verification|verify|verifying/i });
    this.loadingSpinner = page.locator(".animate-spin");
    this.explanationSection = page.getByText("How Hash Chain Verification Works");
    this.securityNote = page.getByText("Security Note");
    this.backLink = page.getByRole("link", { name: /back to overview/i });
  }

  async goto(): Promise<void> {
    await this.page.goto("/compliance/verification");
    await this.page.waitForLoadState("networkidle");
  }

  async expectLoaded(): Promise<void> {
    await expect(this.heading).toBeVisible({ timeout: config.timeout.navigation });
  }

  async expectValid(): Promise<void> {
    await expect(this.statusTextValid).toBeVisible();
  }

  async expectInvalid(): Promise<void> {
    await expect(this.statusTextInvalid).toBeVisible();
  }

  async expectBreakAt(recordNum: number): Promise<void> {
    await expect(this.breakLocationSection).toBeVisible();
    await expect(this.page.getByText(`Record #${recordNum}`)).toBeVisible();
  }

  async getTotalRecords(): Promise<number> {
    const text = await this.totalRecordsValue.textContent();
    return parseInt(text || "0");
  }

  async clickReVerify(): Promise<void> {
    await this.reVerifyButton.click();
  }

  async waitForVerificationComplete(): Promise<void> {
    // Wait for spinner to disappear
    await expect(this.loadingSpinner).not.toBeVisible({ timeout: config.timeout.apiResponse });
  }

  async navigateBack(): Promise<void> {
    await this.backLink.click();
    await this.page.waitForURL(/\/compliance$/);
  }
}

/**
 * Compliance Version Bundles Page
 * Route: /compliance/version-bundles
 */
export class ComplianceVersionBundlesPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly bundleListSection: Locator;
  readonly bundleDetailSection: Locator;
  readonly bundleListItems: Locator;
  readonly snapshotCount: Locator;
  readonly loadingIndicator: Locator;
  readonly detailLoadingIndicator: Locator;
  readonly emptyState: Locator;
  readonly selectPrompt: Locator;
  readonly explanationSection: Locator;
  readonly backLink: Locator;

  constructor(page: Page) {
    this.page = page;
    // Use exact match to avoid matching "Why Version Bundles Matter"
    this.heading = page.getByRole("heading", { name: "Version Bundles", exact: true });
    this.bundleListSection = page.locator(".bg-card").filter({ hasText: "Pipeline Runs" });
    this.bundleDetailSection = page.locator(".bg-card").filter({ hasText: "Bundle Details" });
    // Bundle list items are buttons containing run IDs
    this.bundleListItems = page.locator("button").filter({ hasText: /^run-/ });
    this.snapshotCount = page.getByText(/\d+ version snapshots? captured/i);
    this.loadingIndicator = page.getByText("Loading version bundles...");
    this.detailLoadingIndicator = page.getByText("Loading...");
    this.emptyState = page.getByText("No version bundles recorded yet");
    this.selectPrompt = page.getByText("Select a run to view version details");
    this.explanationSection = page.getByText("Why Version Bundles Matter");
    this.backLink = page.getByRole("link", { name: /back to overview/i });
  }

  async goto(): Promise<void> {
    await this.page.goto("/compliance/version-bundles");
    await this.page.waitForLoadState("networkidle");
  }

  async expectLoaded(): Promise<void> {
    await expect(this.heading).toBeVisible({ timeout: config.timeout.navigation });
  }

  async getBundleCount(): Promise<number> {
    return await this.bundleListItems.count();
  }

  async selectBundle(runId: string): Promise<void> {
    await this.page.locator(`button:has-text("${runId}")`).click();
    await this.page.waitForLoadState("networkidle");
  }

  async selectFirstBundle(): Promise<void> {
    await this.bundleListItems.first().click();
    await this.page.waitForLoadState("networkidle");
  }

  async expectBundleSelected(): Promise<void> {
    await expect(this.selectPrompt).not.toBeVisible();
  }

  async expectDetailField(label: string, valuePattern?: RegExp): Promise<void> {
    // Use exact match to avoid matching similar labels like "Model" vs "Model Version"
    const labelLocator = this.bundleDetailSection.getByText(label, { exact: true });
    await expect(labelLocator).toBeVisible();

    if (valuePattern) {
      // Find the value next to the label
      const row = labelLocator.locator("..");
      await expect(row).toHaveText(valuePattern);
    }
  }

  async expectDirtyBadge(): Promise<void> {
    await expect(this.page.locator("span").filter({ hasText: "dirty" })).toBeVisible();
  }

  async expectCleanStatus(): Promise<void> {
    await expect(this.bundleDetailSection.getByText("Clean")).toBeVisible();
  }

  async expectDirtyStatus(): Promise<void> {
    await expect(
      this.bundleDetailSection.getByText("Dirty (uncommitted changes)")
    ).toBeVisible();
  }

  async navigateBack(): Promise<void> {
    await this.backLink.click();
    await this.page.waitForURL(/\/compliance$/);
  }
}

/**
 * Compliance Controls Page
 * Route: /compliance/controls
 */
export class ComplianceControlsPage {
  readonly page: Page;
  readonly heading: Locator;
  readonly progressCircle: Locator;
  readonly progressPercentage: Locator;
  readonly implementedCount: Locator;
  readonly controlCategories: Locator;
  readonly talkingPointsSection: Locator;
  readonly backLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.heading = page.getByRole("heading", { name: "Control Mapping" });
    this.progressCircle = page.locator(".w-24.h-24");
    this.progressPercentage = page.locator(".text-3xl.font-bold.text-green-500");
    this.implementedCount = page.locator("text=/\\d+ of \\d+ control categories/i");
    this.controlCategories = page.locator(".bg-card").filter({ has: page.locator("text=/Implemented|Planned/i") });
    this.talkingPointsSection = page.locator(".bg-blue-500\\/10").filter({ hasText: "Demo Talking Points" });
    this.backLink = page.getByRole("link", { name: /back to overview/i });
  }

  async goto(): Promise<void> {
    await this.page.goto("/compliance/controls");
    await this.page.waitForLoadState("networkidle");
  }

  async expectLoaded(): Promise<void> {
    await expect(this.heading).toBeVisible({ timeout: config.timeout.navigation });
  }

  async getProgressPercentage(): Promise<number> {
    const text = await this.progressPercentage.textContent();
    return parseInt(text?.replace("%", "") || "0");
  }

  async expectProgressPercentage(pct: number): Promise<void> {
    await expect(this.progressPercentage).toHaveText(`${pct}%`);
  }

  async getCategoryCount(): Promise<number> {
    return await this.controlCategories.count();
  }

  async expectCategoryStatus(
    categoryName: string,
    status: "Implemented" | "Planned"
  ): Promise<void> {
    const category = this.page.locator(".bg-card").filter({ hasText: categoryName });
    await expect(category.locator(`text=${status}`)).toBeVisible();
  }

  async clickCategoryViewLink(categoryName: string): Promise<void> {
    const category = this.page.locator(".bg-card").filter({ hasText: categoryName });
    await category.getByRole("link", { name: "View →" }).first().click();
  }

  async expectTalkingPoints(): Promise<void> {
    await expect(this.talkingPointsSection).toBeVisible();
    await expect(this.page.getByText("Tamper-evident audit trail")).toBeVisible();
    await expect(this.page.getByText("Full version traceability")).toBeVisible();
  }

  async navigateBack(): Promise<void> {
    await this.backLink.click();
    await this.page.waitForURL(/\/compliance$/);
  }
}
