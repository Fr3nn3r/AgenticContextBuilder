import { Page, Locator } from "@playwright/test";

export class BasePage {
  readonly page: Page;
  readonly header: Locator;

  constructor(page: Page) {
    this.page = page;
    this.header = page.locator("header");
  }

  async waitForLoad() {
    // Wait for the app to finish loading by waiting for claims data or page content
    await this.page.waitForLoadState("networkidle");
  }

  async getPageTitle(): Promise<string> {
    const h1 = this.header.locator("h1").first();
    return (await h1.textContent()) ?? "";
  }
}
