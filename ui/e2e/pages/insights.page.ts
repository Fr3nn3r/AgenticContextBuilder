import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class InsightsPage extends BasePage {
  readonly batchContextBar: Locator;
  readonly batchSelector: Locator;
  readonly runMetadata: Locator;
  readonly kpiRow: Locator;
  readonly kpiCards: Locator;
  readonly docTypeScoreboard: Locator;

  constructor(page: Page) {
    super(page);
    this.batchContextBar = page.getByTestId("batch-context-bar");
    this.batchSelector = page.getByTestId("batch-context-selector");
    this.runMetadata = page.getByTestId("run-metadata");
    this.kpiRow = page.getByTestId("kpi-row");
    this.kpiCards = page.getByTestId(/kpi-/);
    this.docTypeScoreboard = page.getByTestId("doc-type-scoreboard");
  }

  async goto() {
    // Navigate to batches first, then use tab to go to benchmark
    await this.page.goto("/batches");
    await this.waitForLoad();
    // Click the benchmark tab
    await this.page.getByTestId("batch-tab-metrics").click();
    await this.waitForLoad();
  }

  async gotoWithBatch(batchId: string) {
    await this.page.goto(`/batches/${batchId}/metrics`);
    await this.waitForLoad();
  }

  async selectBatch(batchId: string) {
    await this.batchSelector.selectOption(batchId);
    await this.page.waitForTimeout(300);
  }

  async getSelectedBatchId(): Promise<string> {
    return await this.batchSelector.inputValue();
  }

  async getRunMetadataText(): Promise<string> {
    if (await this.runMetadata.isVisible()) {
      return (await this.runMetadata.textContent()) ?? "";
    }
    return "";
  }
}
