import { Page, Locator } from "@playwright/test";

export class SidebarPage {
  readonly page: Page;
  readonly sidebar: Locator;
  readonly logo: Locator;
  readonly dashboardLink: Locator;
  readonly claimsLink: Locator;
  readonly templatesLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.sidebar = page.locator(".bg-gray-900");
    this.logo = page.locator("text=ContextBuilder");
    this.dashboardLink = page.getByRole("link", { name: /Dashboard/i });
    this.claimsLink = page.getByRole("link", { name: /Claim Document Pack/i });
    this.templatesLink = page.getByRole("link", { name: /Extraction Templates/i });
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

  async isVisible(): Promise<boolean> {
    return await this.sidebar.isVisible();
  }
}
