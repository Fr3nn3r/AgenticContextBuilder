import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class DashboardPage extends BasePage {
  readonly totalClaimsCard: Locator;
  readonly pendingReviewCard: Locator;
  readonly highRiskCard: Locator;
  readonly totalValueCard: Locator;
  readonly riskOverview: Locator;
  readonly reviewProgress: Locator;

  constructor(page: Page) {
    super(page);
    this.totalClaimsCard = page.getByText("Total Claims").locator("..");
    this.pendingReviewCard = page.getByText("Pending Review").locator("..");
    this.highRiskCard = page.getByText("High Risk").locator("..");
    this.totalValueCard = page.getByText("Total Value").locator("..");
    this.riskOverview = page.getByText("Risk Overview");
    this.reviewProgress = page.getByText("Review Progress");
  }

  async goto() {
    await this.page.goto("/dashboard");
    await this.waitForLoad();
  }

  async getTotalClaimsValue(): Promise<string> {
    const value = this.totalClaimsCard.locator(".text-2xl, .text-3xl").first();
    return (await value.textContent()) ?? "";
  }

  async getPendingReviewValue(): Promise<string> {
    const value = this.pendingReviewCard.locator(".text-2xl, .text-3xl").first();
    return (await value.textContent()) ?? "";
  }
}
