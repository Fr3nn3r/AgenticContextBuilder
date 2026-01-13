import { Page, Locator } from "@playwright/test";

export class SidebarPage {
  readonly page: Page;
  readonly sidebar: Locator;
  readonly logo: Locator;
  readonly dashboardLink: Locator;
  readonly claimsLink: Locator;
  readonly insightsLink: Locator;
  readonly templatesLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.sidebar = page.getByTestId("sidebar");
    this.logo = page.getByText("ContextBuilder", { exact: true });
    this.dashboardLink = page.getByTestId("nav-dashboard");
    this.claimsLink = page.getByTestId("nav-claims");
    this.insightsLink = page.getByTestId("nav-insights");
    this.templatesLink = page.getByTestId("nav-templates");
  }

  async navigateToDashboard() {
    await this.dashboardLink.click();
    await this.page.waitForURL("**/dashboard");
  }

  async navigateToClaims() {
    await this.claimsLink.click();
    await this.page.waitForURL("**/claims");
  }

  async navigateToTemplates() {
    await this.templatesLink.click();
    await this.page.waitForURL("**/templates");
  }

  async navigateToInsights() {
    await this.insightsLink.click();
    await this.page.waitForURL("**/insights");
  }

  async isVisible(): Promise<boolean> {
    return await this.sidebar.isVisible();
  }
}
