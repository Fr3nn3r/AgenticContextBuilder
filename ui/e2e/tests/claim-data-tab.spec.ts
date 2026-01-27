import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Claim Data Tab", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  /**
   * Helper to navigate to a claim and open the Data tab
   */
  async function goToDataTab(page: import("@playwright/test").Page, claimId: string) {
    await page.goto(`/claims/${claimId}`);
    // Wait for the page to load
    await page.waitForLoadState("networkidle");
    // Click the Data tab button
    const dataTab = page.getByRole("button", { name: "Data" });
    await dataTab.click();
    // Wait for claim runs to load
    await page.waitForTimeout(500);
  }

  test("should display Data tab icon in tab bar", async ({ page }) => {
    await page.goto("/claims/CLM-2024-001");
    await page.waitForLoadState("networkidle");

    // Data tab should be visible with the Database icon
    const dataTab = page.getByRole("button", { name: "Data" });
    await expect(dataTab).toBeVisible();
  });

  test("should show claim run selector when Data tab is clicked", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");

    // Should show "Claim Run:" label and dropdown
    await expect(page.getByText("Claim Run:")).toBeVisible();
    // Should have a select element
    const selector = page.locator("select");
    await expect(selector).toBeVisible();
  });

  test("should display formatted timestamps in run selector", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");

    // Should show formatted date (e.g., "15 Jan 2026, 10:30")
    await expect(page.getByText(/\d{2} \w{3} \d{4}/)).toBeVisible();
  });

  test("should show gate status card with warn status", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");

    // Wait for data to load
    await page.waitForTimeout(500);

    // Should show "Reconciliation Status" header
    await expect(page.getByText("Reconciliation Status")).toBeVisible();

    // Should show WARN badge (from fixture)
    await expect(page.getByText("WARN")).toBeVisible();
  });

  test("should display conflict count metric", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show "1 conflict" (from fixture)
    await expect(page.getByText(/1 conflict/)).toBeVisible();
  });

  test("should display missing critical facts metric", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show missing critical count (from fixture: 1 missing - vehicle_vin)
    await expect(page.getByText(/1 missing critical/)).toBeVisible();
  });

  test("should display fact count metric", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show "5 facts" (from fixture)
    await expect(page.getByText(/5 facts/)).toBeVisible();
  });

  test("should display coverage percentage metric", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show 85% coverage (from fixture)
    await expect(page.getByText("85% coverage")).toBeVisible();
  });

  test("should display gate status reasons", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show reasons section
    await expect(page.getByText("Reasons")).toBeVisible();

    // Should show specific reason text (from fixture)
    await expect(page.getByText(/Missing critical fact/)).toBeVisible();
  });

  test("should display missing critical facts list", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show "Missing Critical Facts" header
    await expect(page.getByText("Missing Critical Facts")).toBeVisible();

    // Should show the missing fact name (vehicle_vin from fixture)
    await expect(page.getByText("vehicle vin")).toBeVisible();
  });

  test("should display conflicts section", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show "Conflicts (1)" header (from fixture)
    await expect(page.getByText(/Conflicts \(1\)/)).toBeVisible();

    // Should show conflict fact name (date_of_loss from fixture)
    await expect(page.getByText("date of loss")).toBeVisible();
  });

  test("should expand conflict to show details", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Click on the conflict to expand it (should already be expanded by default)
    // Look for the conflict row button
    const conflictButton = page.getByRole("button", { name: /date of loss/ });

    // If not already expanded, click to expand
    if (await conflictButton.isVisible()) {
      // Check if values are visible (expanded state)
      const valueVisible = await page.getByText('"2024-01-10"').isVisible();
      if (!valueVisible) {
        await conflictButton.click();
        await page.waitForTimeout(300);
      }
    }

    // Should show the conflicting values
    await expect(page.getByText('"2024-01-10"')).toBeVisible();
    await expect(page.getByText('"2024-01-09"')).toBeVisible();
  });

  test("should highlight selected value in conflict", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // The selected value should be highlighted with blue styling
    // Look for the "Selected:" label and value
    await expect(page.getByText("Selected:")).toBeVisible();

    // Should show selection confidence
    await expect(page.getByText(/95% confidence/)).toBeVisible();
  });

  test("should show View button on conflict sources", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should have View buttons to navigate to source documents
    const viewButtons = page.getByRole("button", { name: "View" });
    await expect(viewButtons.first()).toBeVisible();
  });

  test("should display All Facts section", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show "All Facts" header
    await expect(page.getByText("All Facts")).toBeVisible();

    // Should show fact count summary (5 facts from fixture)
    await expect(page.getByText(/5 facts from/)).toBeVisible();
  });

  test("should group facts by document type", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show doc_type groups (from fixture: loss_notice, police_report, insurance_policy)
    await expect(page.getByText("loss notice")).toBeVisible();
  });

  test("should display individual fact names and values", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show fact names (from fixture)
    await expect(page.getByText("claimant name")).toBeVisible();
    await expect(page.getByText("policy number")).toBeVisible();

    // Should show fact values
    await expect(page.getByText("John Smith")).toBeVisible();
    await expect(page.getByText("POL-2024-12345")).toBeVisible();
  });

  test("should show stages completed count", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");
    await page.waitForTimeout(500);

    // Should show stages completed (from fixture: 3 stages)
    await expect(page.getByText("3 stages")).toBeVisible();
  });

  test("should allow switching between claim runs", async ({ page }) => {
    await goToDataTab(page, "CLM-2024-001");

    // Get the select element
    const selector = page.locator("select");
    await expect(selector).toBeVisible();

    // Should have multiple options (2 from fixture)
    const options = selector.locator("option");
    expect(await options.count()).toBe(2);

    // First option should have "(latest)" indicator
    await expect(options.first()).toContainText("(latest)");
  });
});

test.describe("Claim Data Tab - No Runs", () => {
  test("should show No Claim Runs message when claim has no runs", async ({ page }) => {
    // Setup mocks with empty claim runs
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ username: "admin", role: "admin" }),
      });
    });

    await page.addInitScript(() => {
      localStorage.setItem("auth_token", "mock-token");
      localStorage.setItem("auth_user", JSON.stringify({ username: "admin", role: "admin" }));
    });

    // Mock claim runs endpoint to return empty array
    await page.route(/\/api\/claims\/[^/]+\/claim-runs$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Mock other necessary endpoints
    await page.route("**/api/claims", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            claim_id: "CLM-NO-RUNS",
            status: "pending",
            created_at: "2024-01-01T00:00:00Z",
            doc_count: 0,
          },
        ]),
      });
    });

    await page.route("**/api/claims/*/review", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ docs: [] }),
      });
    });

    await page.route("**/api/claims/*/facts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ facts: [], sources: [] }),
      });
    });

    await page.route("**/api/claims/*/assessment", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not found" }),
      });
    });

    await page.route("**/api/claims/*/assessment/history", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/claims/CLM-NO-RUNS");
    await page.waitForLoadState("networkidle");

    // Click the Data tab
    const dataTab = page.getByRole("button", { name: "Data" });
    await dataTab.click();
    await page.waitForTimeout(500);

    // Should show "No Claim Runs" message
    await expect(page.getByText("No Claim Runs")).toBeVisible();
    await expect(page.getByText(/Run the reconciliation pipeline/)).toBeVisible();
  });
});

test.describe("Claim Data Tab - No Report", () => {
  test("should show no reconciliation report message when run has no report", async ({ page }) => {
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ username: "admin", role: "admin" }),
      });
    });

    await page.addInitScript(() => {
      localStorage.setItem("auth_token", "mock-token");
      localStorage.setItem("auth_user", JSON.stringify({ username: "admin", role: "admin" }));
    });

    // Mock claim runs with a run
    await page.route(/\/api\/claims\/[^/]+\/claim-runs$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            claim_run_id: "run-no-report",
            created_at: "2026-01-15T10:30:00Z",
            stages_completed: ["aggregate"],
            extraction_runs_considered: [],
          },
        ]),
      });
    });

    // Mock facts endpoint to return empty
    await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/facts$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ facts: [], sources: [] }),
      });
    });

    // Mock reconciliation report to return null/404
    await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/reconciliation-report$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(null),
      });
    });

    // Mock other necessary endpoints
    await page.route("**/api/claims", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            claim_id: "CLM-NO-REPORT",
            status: "pending",
            created_at: "2024-01-01T00:00:00Z",
            doc_count: 1,
          },
        ]),
      });
    });

    await page.route("**/api/claims/*/review", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ docs: [] }),
      });
    });

    await page.route("**/api/claims/*/facts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ facts: [], sources: [] }),
      });
    });

    await page.route("**/api/claims/*/assessment", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not found" }),
      });
    });

    await page.route("**/api/claims/*/assessment/history", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    await page.goto("/claims/CLM-NO-REPORT");
    await page.waitForLoadState("networkidle");

    // Click the Data tab
    const dataTab = page.getByRole("button", { name: "Data" });
    await dataTab.click();
    await page.waitForTimeout(500);

    // Should show run selector but no reconciliation report message
    await expect(page.getByText("Claim Run:")).toBeVisible();
    await expect(page.getByText(/No reconciliation report available|No Data Available/)).toBeVisible();
  });
});

test.describe("Claim Data Tab - Gate Status Variants", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ username: "admin", role: "admin" }),
      });
    });

    await page.addInitScript(() => {
      localStorage.setItem("auth_token", "mock-token");
      localStorage.setItem("auth_user", JSON.stringify({ username: "admin", role: "admin" }));
    });

    // Mock base endpoints
    await page.route("**/api/claims", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { claim_id: "CLM-GATE-TEST", status: "pending", doc_count: 1 },
        ]),
      });
    });

    await page.route("**/api/claims/*/review", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ docs: [] }),
      });
    });

    await page.route("**/api/claims/*/facts", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ facts: [], sources: [] }),
      });
    });

    await page.route("**/api/claims/*/assessment", async (route) => {
      await route.fulfill({ status: 404 });
    });

    await page.route("**/api/claims/*/assessment/history", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Mock claim runs
    await page.route(/\/api\/claims\/[^/]+\/claim-runs$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            claim_run_id: "run-gate-test",
            created_at: "2026-01-15T10:30:00Z",
            stages_completed: ["aggregate", "reconcile", "gate"],
            extraction_runs_considered: [],
          },
        ]),
      });
    });

    await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/facts$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ facts: [], sources: [] }),
      });
    });
  });

  test("should show green card for PASS gate status", async ({ page }) => {
    await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/reconciliation-report$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          gate: {
            status: "pass",
            missing_critical_facts: [],
            conflict_count: 0,
            provenance_coverage: 1.0,
            estimated_tokens: 500,
            reasons: [],
          },
          conflicts: [],
          fact_count: 10,
        }),
      });
    });

    await page.goto("/claims/CLM-GATE-TEST");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Data" }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText("PASS")).toBeVisible();
    await expect(page.getByText("0 conflicts")).toBeVisible();
    await expect(page.getByText("100% coverage")).toBeVisible();
  });

  test("should show red card for FAIL gate status", async ({ page }) => {
    await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/reconciliation-report$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          gate: {
            status: "fail",
            missing_critical_facts: ["date_of_loss", "claimant_name", "policy_number"],
            conflict_count: 5,
            provenance_coverage: 0.3,
            estimated_tokens: 200,
            reasons: ["Too many missing critical facts", "Coverage below threshold"],
          },
          conflicts: [],
          fact_count: 2,
        }),
      });
    });

    await page.goto("/claims/CLM-GATE-TEST");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: "Data" }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText("FAIL")).toBeVisible();
    await expect(page.getByText("5 conflicts")).toBeVisible();
    await expect(page.getByText("3 missing critical")).toBeVisible();
    await expect(page.getByText("30% coverage")).toBeVisible();
  });
});
