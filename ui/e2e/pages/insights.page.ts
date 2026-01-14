import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class InsightsPage extends BasePage {
  readonly batchContextBar: Locator;
  readonly batchSelector: Locator;
  readonly runMetadata: Locator;
  readonly kpiCards: Locator;
  readonly insightsTab: Locator;
  readonly historyTab: Locator;
  readonly compareTab: Locator;

  constructor(page: Page) {
    super(page);
    this.batchContextBar = page.getByTestId("batch-context-bar");
    this.batchSelector = page.getByTestId("batch-context-selector");
    this.runMetadata = page.getByTestId("run-metadata");
    this.kpiCards = page.locator(".rounded-lg.border.p-3");
    this.insightsTab = page.getByRole("button", { name: "Insights" });
    this.historyTab = page.getByRole("button", { name: "Batch History" });
    this.compareTab = page.getByRole("button", { name: "Compare Batches" });
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

  async switchToTab(tab: "insights" | "history" | "compare") {
    const tabMap = {
      insights: this.insightsTab,
      history: this.historyTab,
      compare: this.compareTab,
    };
    await tabMap[tab].click();
    await this.page.waitForTimeout(300);
  }
}
