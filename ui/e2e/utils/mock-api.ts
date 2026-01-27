import { Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load fixtures
const fixturesDir = path.join(__dirname, "..", "fixtures");
const claimsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "claims.json"), "utf-8"));
const claimReviewFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "claim-review.json"), "utf-8"));
const docPayloadFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "doc-payload.json"), "utf-8"));
const templatesFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "templates.json"), "utf-8"));
const batchesFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "runs.json"), "utf-8"));
const insightsOverviewFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "insights-overview.json"), "utf-8"));
const multiBatchFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "multi-run-data.json"), "utf-8"));
const usersFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "users.json"), "utf-8"));
const classificationDocsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "classification-docs.json"), "utf-8"));
const pendingClaimsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "pending-claims.json"), "utf-8"));
const uploadResultFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "upload-result.json"), "utf-8"));
const pipelineRunFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "pipeline-run.json"), "utf-8"));
const pipelineStatusFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "pipeline-status.json"), "utf-8"));
const claimRunsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "claim-runs.json"), "utf-8"));
const claimFactsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "claim-facts.json"), "utf-8"));
const reconciliationReportFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "reconciliation-report.json"), "utf-8"));

// Compliance fixtures
const complianceDecisionsFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "compliance-decisions.json"), "utf-8")
);
const complianceVerificationFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "compliance-verification.json"), "utf-8")
);
const complianceBundlesFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "compliance-bundles.json"), "utf-8")
);

// Auth types
export type Role = "admin" | "reviewer" | "operator" | "auditor";
export interface User {
  username: string;
  role: Role;
}

export async function setupApiMocks(page: Page) {
  // Mock GET /api/claims - ensure claims have in_run: true for batch-scoped views
  await page.route("**/api/claims", async (route) => {
    if (route.request().method() === "GET") {
      // Add in_run: true to all claims so they appear in batch-scoped views
      const claimsWithInRun = claimsFixture.map((c: Record<string, unknown>) => ({
        ...c,
        in_run: true,
      }));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(claimsWithInRun),
      });
    } else {
      await route.continue();
    }
  });

  // Mock upload pending claims list
  await page.route("**/api/upload/pending", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(pendingClaimsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock upload claim endpoints (POST upload, GET claim, DELETE claim)
  await page.route(/\/api\/upload\/claim\/[^/]+$/, async (route) => {
    const method = route.request().method();
    if (method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(uploadResultFixture),
      });
      return;
    }
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(pendingClaimsFixture[0] || uploadResultFixture),
      });
      return;
    }
    if (method === "DELETE") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "deleted" }),
      });
      return;
    }
    await route.continue();
  });

  // Mock upload document delete endpoint
  await page.route(/\/api\/upload\/claim\/[^/]+\/doc\/[^/]+$/, async (route) => {
    if (route.request().method() === "DELETE") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "deleted" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock pipeline run start
  await page.route("**/api/pipeline/run", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(pipelineRunFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock pipeline cancel
  await page.route(/\/api\/pipeline\/cancel\/[^/]+$/, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "cancelled" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock pipeline status
  await page.route(/\/api\/pipeline\/status\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(pipelineStatusFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/claims/:claimId/docs (with optional query params)
  await page.route(/\/api\/claims\/[^/]+\/docs(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(claimReviewFixture.docs),
    });
  });

  // Mock GET /api/classification/docs (with optional query params)
  await page.route(/\/api\/classification\/docs(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(classificationDocsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/classification/doc/:docId/label
  await page.route("**/api/classification/doc/*/label", async (route) => {
    if (route.request().method() === "POST") {
      const docId = route.request().url().split("/").slice(-2)[0];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved", doc_id: docId }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/classification/stats (with optional query params)
  await page.route(/\/api\/classification\/stats(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          docs_total: classificationDocsFixture.length,
          docs_reviewed: classificationDocsFixture.filter((d: { review_status: string }) => d.review_status !== "pending").length,
          overrides_count: 0,
          avg_confidence: 0.83,
          by_predicted_type: {},
          confusion_matrix: [],
        }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/claims/:claimId/review
  await page.route("**/api/claims/*/review", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(claimReviewFixture),
    });
  });

  // Mock GET /api/docs/:docId (but not /labels or /source)
  await page.route(/\/api\/docs\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(docPayloadFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/docs/:docId/labels
  await page.route("**/api/docs/*/labels", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved", path: "/mock/path" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/documents (for DocumentsListPage)
  await page.route(/\/api\/documents(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      // Return documents with has_truth field for the documents list page
      const documents = [
        {
          doc_id: "doc_001",
          claim_id: "CLM-2024-001",
          filename: "loss_notice.pdf",
          doc_type: "loss_notice",
          language: "en",
          has_truth: false,
          last_reviewed: null,
          reviewer: null,
          quality_status: "pass",
        },
        {
          doc_id: "doc_002",
          claim_id: "CLM-2024-001",
          filename: "police_report.pdf",
          doc_type: "police_report",
          language: "en",
          has_truth: true,
          last_reviewed: "2024-01-15T10:00:00Z",
          reviewer: "admin",
          quality_status: "warn",
        },
        {
          doc_id: "doc_003",
          claim_id: "CLM-2024-001",
          filename: "insurance_policy.pdf",
          doc_type: "insurance_policy",
          language: "en",
          has_truth: false,
          last_reviewed: null,
          reviewer: null,
          quality_status: "fail",
        },
      ];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ documents, total: documents.length }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/templates
  await page.route("**/api/templates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(templatesFixture),
    });
  });

  // Mock GET /api/runs/latest
  await page.route("**/api/runs/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_dir: "runs/latest",
        total_claims: 2,
        total_docs: 5,
        extracted_count: 5,
        labeled_count: 3,
        quality_gate: { pass: 2, warn: 2, fail: 1 },
      }),
    });
  });

  // Mock GET /api/insights/batches (also handles legacy /api/insights/runs)
  await page.route(/\/api\/insights\/(runs|batches)$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(batchesFixture),
    });
  });

  // Mock GET /api/insights/runs/detailed and /api/insights/batches/detailed
  await page.route(/\/api\/insights\/(runs|batches)\/detailed/, async (route) => {
    // Return detailed batch info (DetailedRunInfo format) with full phases structure
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(batchesFixture.map((b: { run_id: string; timestamp: string; model: string; docs_count?: number }) => {
        const docsTotal = b.docs_count || 5;
        return {
          run_id: b.run_id,
          timestamp: b.timestamp,
          model: b.model,
          status: "complete" as const,
          duration_seconds: 120,
          claims_count: 2,
          docs_total: docsTotal,
          docs_success: Math.floor(docsTotal * 0.8),
          docs_failed: Math.floor(docsTotal * 0.2),
          phases: {
            ingestion: {
              discovered: docsTotal,
              ingested: docsTotal,
              skipped: 0,
              failed: 0,
              duration_ms: 5000,
            },
            classification: {
              classified: docsTotal,
              low_confidence: 0,
              distribution: { loss_notice: 2, police_report: 2, invoice: 1 },
              duration_ms: 3000,
            },
            extraction: {
              attempted: docsTotal,
              succeeded: Math.floor(docsTotal * 0.8),
              failed: Math.floor(docsTotal * 0.2),
              skipped_unsupported: 0,
              duration_ms: 10000,
            },
            quality_gate: {
              pass: Math.floor(docsTotal * 0.6),
              warn: Math.floor(docsTotal * 0.2),
              fail: Math.floor(docsTotal * 0.2),
            },
          },
        };
      })),
    });
  });

  // Mock GET /api/insights/(runs|batch)/:id/overview
  await page.route(/\/api\/insights\/(run|batch)\/[^/]+\/overview/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(insightsOverviewFixture),
    });
  });

  // Mock GET /api/insights/(runs|batch)/:id/doc-types
  await page.route(/\/api\/insights\/(run|batch)\/[^/]+\/doc-types/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          doc_type: "loss_notice",
          docs_reviewed: 2,
          required_field_presence_pct: 90,
          required_field_accuracy_pct: 95,
          evidence_rate_pct: 85,
          top_failing_field: null,
          docs_needs_vision: 0,
        },
        {
          doc_type: "police_report",
          docs_reviewed: 1,
          required_field_presence_pct: 75,
          required_field_accuracy_pct: 80,
          evidence_rate_pct: 70,
          top_failing_field: "badge_number",
          docs_needs_vision: 1,
        },
      ]),
    });
  });

  // Mock GET /api/insights/(run|batch)/:id/priorities
  await page.route(/\/api\/insights\/(run|batch)\/[^/]+\/priorities/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Mock GET /api/insights/baseline
  await page.route("**/api/insights/baseline", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ baseline_run_id: null }),
    });
  });

  // Mock GET /api/claims/batches and /api/claims/runs (legacy)
  await page.route(/\/api\/(claim-runs|claims\/(batches|runs))/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(batchesFixture),
    });
  });

  // Mock GET /api/claims/:claimId/claim-runs (list claim runs for a claim)
  await page.route(/\/api\/claims\/[^/]+\/claim-runs$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(claimRunsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/claims/:claimId/claim-runs/:runId/facts
  await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/facts$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(claimFactsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/claims/:claimId/claim-runs/:runId/reconciliation-report
  await page.route(/\/api\/claims\/[^/]+\/claim-runs\/[^/]+\/reconciliation-report$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(reconciliationReportFixture),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Setup API mocks for multi-batch testing scenarios.
 * This function mocks APIs with batch-specific data to test that UI
 * correctly displays batch-scoped metrics when switching between batches.
 */
export async function setupMultiBatchMocks(page: Page) {
  // Mock GET /api/claims (same as base)
  await page.route("**/api/claims", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(claimsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/insights/batches - return multi-batch data
  await page.route(/\/api\/insights\/(runs|batches)$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(multiBatchFixture.batches),
    });
  });

  // Mock GET /api/insights/batches/detailed
  await page.route(/\/api\/insights\/(runs|batches)\/detailed/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(multiBatchFixture.detailedBatches),
    });
  });

  // Mock GET /api/insights/batch/:batchId/overview - return batch-specific data
  await page.route(/\/api\/insights\/(run|batch)\/([^/]+)\/overview/, async (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/insights\/(?:run|batch)\/([^/]+)\/overview/);
    const batchId = match ? match[1] : "batch-small";

    const overview = multiBatchFixture.overviews[batchId] || multiBatchFixture.overviews["batch-small"];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(overview),
    });
  });

  // Mock GET /api/insights/batch/:batchId/doc-types - return batch-specific data
  await page.route(/\/api\/insights\/(run|batch)\/([^/]+)\/doc-types/, async (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/insights\/(?:run|batch)\/([^/]+)\/doc-types/);
    const batchId = match ? match[1] : "batch-small";

    const docTypes = multiBatchFixture.docTypes[batchId] || multiBatchFixture.docTypes["batch-small"];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(docTypes),
    });
  });

  // Mock GET /api/insights/batch/:batchId/priorities - return empty for simplicity
  await page.route(/\/api\/insights\/(run|batch)\/([^/]+)\/priorities/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Mock GET /api/insights/baseline
  await page.route("**/api/insights/baseline", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ baseline_batch_id: null }),
    });
  });

  // Mock GET /api/claims/batches - for Extraction page batch selector
  await page.route(/\/api\/claims\/(runs|batches)/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(multiBatchFixture.batches.map((b: { run_id: string; timestamp: string; model: string; claims_count: number }) => ({
        run_id: b.run_id,
        timestamp: b.timestamp,
        model: b.model,
        claims_count: b.claims_count,
      }))),
    });
  });

  // Mock GET /api/templates
  await page.route("**/api/templates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(templatesFixture),
    });
  });
}

// Legacy alias for backwards compatibility
export const setupMultiRunMocks = setupMultiBatchMocks;

/**
 * Setup auth mocks for authenticated user.
 * Sets up localStorage with auth token and user data, and mocks auth endpoints.
 */
export async function setupAuthMocks(page: Page, role: Role = "admin") {
  const user = usersFixture[role] as User;
  const token = `mock-token-${role}-${Date.now()}`;

  // Set localStorage before navigation
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem("auth_token", token);
    localStorage.setItem("auth_user", JSON.stringify(user));
  }, { token, user });

  // Mock GET /api/auth/me - returns current user
  await page.route("**/api/auth/me", async (route) => {
    const authHeader = route.request().headers()["authorization"];
    if (authHeader && authHeader.startsWith("Bearer ")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(user),
      });
    } else {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
    }
  });

  // Mock POST /api/auth/login
  await page.route("**/api/auth/login", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      const requestedUser = Object.values(usersFixture).find(
        (u: User) => u.username === body.username
      ) as User | undefined;

      if (requestedUser && body.password === "password") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            token: `mock-token-${requestedUser.role}-${Date.now()}`,
            user: requestedUser,
          }),
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid credentials" }),
        });
      }
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/auth/logout
  await page.route("**/api/auth/logout", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "logged_out" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/admin/users (admin only)
  await page.route("**/api/admin/users", async (route) => {
    if (route.request().method() === "GET") {
      if (role === "admin") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(Object.values(usersFixture)),
        });
      } else {
        await route.fulfill({
          status: 403,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Admin access required" }),
        });
      }
    } else {
      await route.continue();
    }
  });
}

/**
 * Setup mocks for unauthenticated state.
 * Used to test login flow - no localStorage token, /api/auth/me returns 401.
 */
export async function setupUnauthenticatedMocks(page: Page) {
  // Clear any existing auth state
  await page.addInitScript(() => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user");
  });

  // Mock GET /api/auth/me - returns 401
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Not authenticated" }),
    });
  });

  // Mock POST /api/auth/login
  await page.route("**/api/auth/login", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      const requestedUser = Object.values(usersFixture).find(
        (u: User) => u.username === body.username
      ) as User | undefined;

      if (requestedUser && body.password === "password") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            token: `mock-token-${requestedUser.role}-${Date.now()}`,
            user: requestedUser,
          }),
        });
      } else {
        await route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Invalid credentials" }),
        });
      }
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/auth/logout
  await page.route("**/api/auth/logout", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "logged_out" }),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Setup all mocks for authenticated user (auth + API mocks combined).
 * This is the most common setup for e2e tests.
 */
export async function setupAuthenticatedMocks(page: Page, role: Role = "admin") {
  await setupAuthMocks(page, role);
  await setupApiMocks(page);
}

/**
 * Setup all mocks for authenticated user with multi-batch data.
 * Use this for tests that need to switch between different batches.
 */
export async function setupAuthenticatedMultiBatchMocks(page: Page, role: Role = "admin") {
  await setupAuthMocks(page, role);
  await setupMultiBatchMocks(page);
}

// ============================================================================
// Compliance Mocks
// ============================================================================

export interface ComplianceMockOptions {
  /** Verification scenario: valid, invalid, or empty hash chain */
  verification?: "valid" | "invalid" | "empty";
  /** Decision list scenario: normal data or empty */
  decisions?: "normal" | "empty";
}

/**
 * Setup compliance endpoint mocks.
 * Can be configured to return different scenarios for testing edge cases.
 *
 * @param page - Playwright page object
 * @param options - Configuration for mock scenarios
 */
export async function setupComplianceMocks(
  page: Page,
  options: ComplianceMockOptions = {}
): Promise<void> {
  const { verification = "valid", decisions = "normal" } = options;

  // Mock GET /api/compliance/ledger/verify
  await page.route("**/api/compliance/ledger/verify", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(complianceVerificationFixture[verification]),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/compliance/ledger/decisions (with filtering support)
  await page.route(/\/api\/compliance\/ledger\/decisions(\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      // Parse query params for filtering
      const url = new URL(route.request().url());
      const typeFilter = url.searchParams.get("decision_type");
      const claimFilter = url.searchParams.get("claim_id");
      const docFilter = url.searchParams.get("doc_id");

      // Start with base data or empty
      let filteredDecisions =
        decisions === "empty" ? [] : [...complianceDecisionsFixture];

      // Apply filters
      if (typeFilter) {
        filteredDecisions = filteredDecisions.filter(
          (d: { decision_type: string }) => d.decision_type === typeFilter
        );
      }
      if (claimFilter) {
        filteredDecisions = filteredDecisions.filter((d: { claim_id?: string }) =>
          d.claim_id?.toLowerCase().includes(claimFilter.toLowerCase())
        );
      }
      if (docFilter) {
        filteredDecisions = filteredDecisions.filter((d: { doc_id?: string }) =>
          d.doc_id?.toLowerCase().includes(docFilter.toLowerCase())
        );
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(filteredDecisions),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/compliance/version-bundles (list)
  await page.route(/\/api\/compliance\/version-bundles$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(complianceBundlesFixture.list),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/compliance/version-bundles/:runId (detail)
  await page.route(/\/api\/compliance\/version-bundles\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      const url = route.request().url();
      const runId = url.split("/").pop();
      const detail =
        complianceBundlesFixture.detail[runId!] ||
        complianceBundlesFixture.detail["run-2026-01-15-001"];

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(detail),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/compliance/config-history
  await page.route("**/api/compliance/config-history", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/compliance/truth-history/:fileMd5
  await page.route(/\/api\/compliance\/truth-history\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ file_md5: "mock", version_count: 0, versions: [] }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/compliance/label-history/:docId
  await page.route(/\/api\/compliance\/label-history\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ doc_id: "mock", version_count: 0, versions: [] }),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Setup all mocks for authenticated user with compliance data.
 * Use this for compliance-specific tests.
 */
export async function setupAuthenticatedComplianceMocks(
  page: Page,
  role: Role = "admin",
  complianceOptions: ComplianceMockOptions = {}
): Promise<void> {
  await setupAuthMocks(page, role);
  await setupApiMocks(page);
  await setupComplianceMocks(page, complianceOptions);
}
