import { Page, Locator } from "@playwright/test";

export class SidebarPage {
  readonly page: Page;
  readonly sidebar: Locator;
  readonly logo: Locator;
  readonly batchesLink: Locator;
  readonly allClaimsLink: Locator;
  readonly templatesLink: Locator;
  readonly pipelineLink: Locator;
  readonly newClaimLink: Locator;
  readonly truthLink: Locator;
  readonly adminLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.sidebar = page.getByTestId("sidebar");
    this.logo = page.getByText("ContextBuilder", { exact: true });
    this.batchesLink = page.getByTestId("nav-batches");
    this.allClaimsLink = page.getByTestId("nav-all-claims");
    this.templatesLink = page.getByTestId("nav-templates");
    this.pipelineLink = page.getByTestId("nav-pipeline");
    this.newClaimLink = page.getByTestId("nav-new-claim");
    this.truthLink = page.getByTestId("nav-truth");
    this.adminLink = page.getByTestId("nav-admin");
  }

  async navigateToBatches() {
    await this.batchesLink.click();
    await this.page.waitForURL("**/batches/**");
  }

  async navigateToAllClaims() {
    await this.allClaimsLink.click();
    await this.page.waitForURL("**/claims/all");
  }

  async navigateToTemplates() {
    await this.templatesLink.click();
    await this.page.waitForURL("**/templates");
  }

  async navigateToPipeline() {
    await this.pipelineLink.click();
    await this.page.waitForURL("**/pipeline");
  }

  async isVisible(): Promise<boolean> {
    return await this.sidebar.isVisible();
  }
}
