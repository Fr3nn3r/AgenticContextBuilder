import { Page, Locator, expect } from "@playwright/test";

export class AuthPage {
  readonly page: Page;
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;
  readonly loadingSpinner: Locator;
  readonly pageTitle: Locator;
  readonly signInText: Locator;

  constructor(page: Page) {
    this.page = page;
    this.usernameInput = page.getByLabel("Username");
    this.passwordInput = page.getByLabel("Password");
    this.submitButton = page.getByRole("button", { name: /sign in/i });
    this.errorMessage = page.locator(".text-destructive");
    this.loadingSpinner = page.locator(".animate-spin");
    this.pageTitle = page.getByRole("heading", { name: "ContextBuilder" });
    this.signInText = page.getByText("Sign in to your account");
  }

  async goto() {
    await this.page.goto("/login");
  }

  async login(username: string, password: string) {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async expectLoginPage() {
    await expect(this.pageTitle).toBeVisible();
    await expect(this.signInText).toBeVisible();
    await expect(this.usernameInput).toBeVisible();
    await expect(this.passwordInput).toBeVisible();
    await expect(this.submitButton).toBeVisible();
  }

  async expectErrorMessage(message?: string) {
    await expect(this.errorMessage).toBeVisible();
    if (message) {
      await expect(this.errorMessage).toContainText(message);
    }
  }

  async expectNoErrorMessage() {
    await expect(this.errorMessage).not.toBeVisible();
  }

  async expectLoading() {
    await expect(this.submitButton).toContainText(/signing in/i);
  }
}

export class AccessDeniedPage {
  readonly page: Page;
  readonly accessDeniedHeading: Locator;
  readonly roleText: Locator;

  constructor(page: Page) {
    this.page = page;
    this.accessDeniedHeading = page.getByRole("heading", { name: "Access Denied" });
    this.roleText = page.locator("text=Your role:");
  }

  async expectAccessDenied() {
    await expect(this.accessDeniedHeading).toBeVisible();
  }

  async expectRole(role: string) {
    await expect(this.roleText).toBeVisible();
    await expect(this.page.locator(`text=${role}`)).toBeVisible();
  }
}
