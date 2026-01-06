import { test, expect } from "@playwright/test";
import { TemplatesPage } from "../pages/templates.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Templates Page", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("should display templates page", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    // Page should load
    await expect(page).toHaveURL(/\/templates/);
  });

  test("should display template cards", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    // Should show templates from fixture (formatted names like "Loss Notice")
    await expect(page.getByRole("button", { name: /Loss Notice/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Police Report/i })).toBeVisible();
  });

  test("displays exactly 3 supported doc types", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    // Should show all 3 supported doc types
    await expect(page.getByRole("button", { name: /Loss Notice/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Police Report/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Insurance Policy/i })).toBeVisible();

    // Count template buttons (should be exactly 3)
    const templateButtons = page.getByRole("button").filter({
      has: page.locator("text=/Loss Notice|Police Report|Insurance Policy/i"),
    });

    // We should have exactly 3 doc type templates
    const count = await templateButtons.count();
    expect(count).toBe(3);
  });

  test("should show template details when selected", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    await templates.selectTemplate("loss_notice");

    // Should show required fields section
    await expect(templates.requiredFieldsSection).toBeVisible();
  });

  test("should show required and optional fields sections", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    await templates.selectTemplate("loss_notice");

    await expect(templates.requiredFieldsSection).toBeVisible();
    await expect(templates.optionalFieldsSection).toBeVisible();
  });

  test("should show quality gate rules", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    await templates.selectTemplate("loss_notice");

    await expect(templates.qualityGateSection).toBeVisible();
  });

  test("should switch between different templates", async ({ page }) => {
    const templates = new TemplatesPage(page);
    await templates.goto();

    // Select first template
    await templates.selectTemplate("loss_notice");
    await expect(templates.requiredFieldsSection).toBeVisible();

    // Select second template
    await templates.selectTemplate("police_report");
    await expect(templates.requiredFieldsSection).toBeVisible();
  });
});
