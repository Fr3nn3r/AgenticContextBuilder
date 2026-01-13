import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class InsightsPage extends BasePage {
  readonly batchSelector: Locator;
  readonly runMetadata: Locator;
  readonly kpiCards: Locator;
  readonly insightsTab: Locator;
  readonly historyTab: Locator;
  readonly compareTab: Locator;

  constructor(page: Page) {
    super(page);
    this.batchSelector = page.getByTestId("batch-selector");
    this.runMetadata = page.getByTestId("run-metadata");
    this.kpiCards = page.locator(".rounded-lg.border.p-3");
    this.insightsTab = page.getByRole("button", { name: "Insights" });
    this.historyTab = page.getByRole("button", { name: "Batch History" });
    this.compareTab = page.getByRole("button", { name: "Compare Batches" });
  }

  async goto() {
    await this.page.goto("/insights");
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
