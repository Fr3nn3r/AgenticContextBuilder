import { test, expect } from "@playwright/test";
import { AuthPage, AccessDeniedPage } from "../pages/auth.page";
import { SidebarPage } from "../pages/sidebar.page";
import {
  setupAuthMocks,
  setupUnauthenticatedMocks,
  setupAuthenticatedMocks,
  type Role,
} from "../utils/mock-api";

test.describe("Login Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupUnauthenticatedMocks(page);
  });

  test("displays login page when not authenticated", async ({ page }) => {
    await page.goto("/batches");

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);

    const authPage = new AuthPage(page);
    await authPage.expectLoginPage();
  });

  test("successful login redirects to batches", async ({ page }) => {
    const authPage = new AuthPage(page);
    await authPage.goto();
    await authPage.expectLoginPage();

    // Login with valid credentials
    await authPage.login("admin", "password");

    // Should redirect to batches
    await expect(page).toHaveURL(/\/batches/);
  });

  test("failed login shows error message", async ({ page }) => {
    const authPage = new AuthPage(page);
    await authPage.goto();

    // Login with invalid credentials
    await authPage.login("admin", "wrongpassword");

    // Wait for network request to complete
    await page.waitForLoadState("networkidle");

    // Should show error message
    await authPage.expectErrorMessage("Invalid credentials");

    // Should stay on login page
    await expect(page).toHaveURL(/\/login/);
  });

  test("login redirects back to original page", async ({ page }) => {
    // Try to access templates page
    await page.goto("/templates");

    // Should redirect to login with original path
    await expect(page).toHaveURL(/\/login/);

    const authPage = new AuthPage(page);
    await authPage.login("admin", "password");

    // Should redirect back to templates
    await expect(page).toHaveURL(/\/templates/);
  });
});

test.describe("Logout Flow", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("logout redirects to login page", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Click sign out button
    await page.getByRole("button", { name: /sign out/i }).click();

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });

  test("session cleared after logout - no auto login on refresh", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Verify we're logged in
    await expect(page.getByTestId("sidebar")).toBeVisible();

    // Logout
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);

    // Setup unauthenticated state for refresh
    await setupUnauthenticatedMocks(page);

    // Refresh and try to access protected page
    await page.goto("/batches");

    // Should redirect to login (not auto-login)
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Session Persistence", () => {
  test("authenticated user stays logged in on page refresh", async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");

    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Verify we're logged in
    await expect(page.getByTestId("sidebar")).toBeVisible();
    // Use more specific selector - username in the user section
    await expect(page.locator(".text-sidebar-foreground.truncate").filter({ hasText: "admin" })).toBeVisible();

    // Refresh the page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Should still be logged in
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });
});

test.describe("Role-Based Access - Admin", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("admin can see all sidebar items", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    const sidebar = new SidebarPage(page);

    // Admin should see all nav items including Admin
    await expect(sidebar.newClaimLink).toBeVisible();
    await expect(sidebar.batchesLink).toBeVisible();
    await expect(sidebar.allClaimsLink).toBeVisible();
    await expect(sidebar.truthLink).toBeVisible();
    await expect(sidebar.templatesLink).toBeVisible();
    await expect(sidebar.pipelineLink).toBeVisible();
    await expect(page.getByTestId("nav-admin")).toBeVisible();
  });

  test("admin can access pipeline page", async ({ page }) => {
    await page.goto("/pipeline");
    await page.waitForLoadState("networkidle");

    // Should not show access denied
    await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();

    // Should show pipeline content
    await expect(page.getByTestId("sidebar")).toBeVisible();
  });

  test("admin can access admin page", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    // Should not show access denied
    await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();
  });
});

test.describe("Role-Based Access - Reviewer", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "reviewer");
  });

  test("reviewer cannot see admin in sidebar", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Reviewer should NOT see Admin nav item
    await expect(page.getByTestId("nav-admin")).not.toBeVisible();

    // But should see other items
    await expect(page.getByTestId("nav-batches")).toBeVisible();
    await expect(page.getByTestId("nav-templates")).toBeVisible();
  });

  test("reviewer cannot access pipeline page", async ({ page }) => {
    await page.goto("/pipeline");
    await page.waitForLoadState("networkidle");

    // Should show access denied
    const accessDenied = new AccessDeniedPage(page);
    await accessDenied.expectAccessDenied();
  });

  test("reviewer cannot access admin page", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    // Should show access denied
    const accessDenied = new AccessDeniedPage(page);
    await accessDenied.expectAccessDenied();
  });

  test("reviewer can access templates page", async ({ page }) => {
    await page.goto("/templates");
    await page.waitForLoadState("networkidle");

    // Should not show access denied
    await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();
  });
});

test.describe("Role-Based Access - Operator", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "operator");
  });

  test("operator can access pipeline page", async ({ page }) => {
    await page.goto("/pipeline");
    await page.waitForLoadState("networkidle");

    // Should not show access denied
    await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();
  });

  test("operator cannot access templates page", async ({ page }) => {
    await page.goto("/templates");
    await page.waitForLoadState("networkidle");

    // Should show access denied
    const accessDenied = new AccessDeniedPage(page);
    await accessDenied.expectAccessDenied();
  });

  test("operator cannot access admin page", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    // Should show access denied
    const accessDenied = new AccessDeniedPage(page);
    await accessDenied.expectAccessDenied();
  });
});

test.describe("Role-Based Access - Auditor", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "auditor");
  });

  test("auditor has view-only access to batches", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Should be able to view batches
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();
  });

  test("auditor cannot access new claim page", async ({ page }) => {
    await page.goto("/claims/new");
    await page.waitForLoadState("networkidle");

    // Should show access denied
    const accessDenied = new AccessDeniedPage(page);
    await accessDenied.expectAccessDenied();
  });

  test("auditor cannot access admin page", async ({ page }) => {
    await page.goto("/admin");
    await page.waitForLoadState("networkidle");

    // Should show access denied
    const accessDenied = new AccessDeniedPage(page);
    await accessDenied.expectAccessDenied();
  });

  test("auditor can access pipeline page for viewing", async ({ page }) => {
    await page.goto("/pipeline");
    await page.waitForLoadState("networkidle");

    // Auditor has view access to pipeline
    await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();
  });
});

test.describe("User Display", () => {
  test("displays correct username and role in sidebar", async ({ page }) => {
    await setupAuthenticatedMocks(page, "reviewer");

    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Should display username (specific selector for username text)
    await expect(page.locator(".text-sidebar-foreground.truncate").filter({ hasText: "reviewer" })).toBeVisible();

    // Should display role (lowercase in the role span)
    await expect(page.locator(".text-muted-foreground.capitalize").filter({ hasText: "reviewer" })).toBeVisible();
  });

  test("displays user initial in avatar", async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");

    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Should display initial "A" for admin in the user avatar
    const avatar = page.locator(".rounded-full.bg-sidebar-accent").filter({ hasText: "A" });
    await expect(avatar).toBeVisible();
  });
});
