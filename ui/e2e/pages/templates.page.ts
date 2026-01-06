import { Page, Locator } from "@playwright/test";
import { BasePage } from "./base.page";

export class TemplatesPage extends BasePage {
  readonly templateCards: Locator;
  readonly requiredFieldsSection: Locator;
  readonly optionalFieldsSection: Locator;
  readonly qualityGateSection: Locator;

  constructor(page: Page) {
    super(page);
    // Template cards are buttons with doc type names
    this.templateCards = page.locator("button").filter({ has: page.locator(".font-medium, .font-semibold") });
    // Use heading role for section headers to be specific
    this.requiredFieldsSection = page.getByRole("heading", { name: "Required" });
    this.optionalFieldsSection = page.getByRole("heading", { name: "Optional" });
    this.qualityGateSection = page.getByText("Quality Gate Rules");
  }

  async goto() {
    await this.page.goto("/templates");
    await this.waitForLoad();
  }

  async selectTemplate(docType: string) {
    // Template cards use formatted names (e.g., "Loss Notice" instead of "loss_notice")
    const formatted = docType.replace(/_/g, " ");
    const template = this.page.getByRole("button", { name: new RegExp(formatted, "i") });
    await template.click();
    await this.page.waitForTimeout(300);
  }

  async getTemplateCount(): Promise<number> {
    // Count buttons that look like template cards
    const cards = this.page.locator('[class*="cursor-pointer"]');
    return await cards.count();
  }

  async isTemplateSelected(): Promise<boolean> {
    // Check if template details are visible
    return await this.requiredFieldsSection.isVisible();
  }
}
