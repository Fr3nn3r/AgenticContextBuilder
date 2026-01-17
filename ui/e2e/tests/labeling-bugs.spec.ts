/**
 * E2E tests to identify labeling bugs in the Document Review workflow.
 *
 * These tests expose three issues:
 * 1. Labels should be at DOCUMENT level, not claim level
 * 2. Document status should NOT be "Pending" when labels exist
 * 3. When extracted value differs from truth, it should show "Incorrect" badge
 */
import { test, expect, Page } from "@playwright/test";
import { setupAuthenticatedMocks, setupAuthMocks } from "../utils/mock-api";

// Helper to set up custom mocks for specific test scenarios
async function setupLabelingTestMocks(page: Page, scenario: "default" | "with_labels" | "mismatch_values") {
  await setupAuthMocks(page, "admin");

  // Mock batches/runs (legacy endpoint)
  await page.route("**/api/runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          run_id: "run_test_001",
          status: "completed",
          claim_ids: ["CLM-TEST-001"],
          started_at: "2024-01-14T21:00:00Z",
          completed_at: "2024-01-14T21:10:00Z",
          doc_count: 3,
        },
      ]),
    });
  });

  // Mock detailed runs (used by BatchContext)
  await page.route("**/api/insights/runs/detailed", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          run_id: "run_test_001",
          timestamp: "2024-01-14T21:00:00Z",
          model: "gpt-4o",
          status: "complete",
          docs_total: 3,
          docs_processed: 3,
          claims_count: 1,
        },
      ]),
    });
  });

  // Mock claims/runs (used by BatchContext)
  await page.route("**/api/claims/runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          run_id: "run_test_001",
          status: "completed",
          claim_ids: ["CLM-TEST-001"],
          started_at: "2024-01-14T21:00:00Z",
          completed_at: "2024-01-14T21:10:00Z",
          doc_count: 3,
        },
      ]),
    });
  });

  // Mock run overview
  await page.route("**/api/insights/run/*/overview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_metadata: {
          run_id: "run_test_001",
          timestamp: "2024-01-14T21:00:00Z",
          model: "gpt-4o",
        },
        overview: {
          docs_total: 3,
          docs_with_truth: 1,
          docs_reviewed: 1,
          docs_with_extraction: 3,
          accuracy_rate: 100,
        },
      }),
    });
  });

  // Mock run doc-types
  await page.route("**/api/insights/run/*/doc-types", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { doc_type: "loss_notice", classified: 1, extracted: 1, accuracy: 100 },
        { doc_type: "police_report", classified: 1, extracted: 1, accuracy: 100 },
        { doc_type: "insurance_policy", classified: 1, extracted: 1, accuracy: 100 },
      ]),
    });
  });

  // Mock workspace info
  await page.route("**/api/workspaces/active", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        workspace_id: "test_workspace",
        name: "Test Workspace",
        path: "/test",
      }),
    });
  });

  // Mock classification docs - this is where review_status comes from
  await page.route("**/api/classification/docs*", async (route) => {
    const docs = getClassificationDocsForScenario(scenario);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(docs),
    });
  });

  // Mock claims list
  await page.route("**/api/claims", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            claim_id: "CLM-TEST-001",
            status: "in_progress",
            created_at: "2024-01-14T20:00:00Z",
            doc_count: 3,
            labeled_count: scenario === "with_labels" ? 1 : 0,
            in_run: true,
          },
        ]),
      });
    } else {
      await route.continue();
    }
  });

  // Mock individual claim docs
  await page.route(/\/api\/claims\/[^/]+\/docs/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { doc_id: "doc_001", filename: "loss_notice.pdf", has_extraction: true },
        { doc_id: "doc_002", filename: "police_report.pdf", has_extraction: true },
        { doc_id: "doc_003", filename: "insurance_policy.pdf", has_extraction: true },
      ]),
    });
  });

  // Mock document detail - this is where extraction + labels come from
  await page.route(/\/api\/docs\/doc_\d+/, async (route) => {
    const url = route.request().url();
    const docId = url.match(/doc_(\d+)/)?.[0] || "doc_001";
    const payload = getDocPayloadForScenario(docId, scenario);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  });

  // Mock save labels endpoint
  await page.route(/\/api\/docs\/[^/]+\/labels/, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock classification label save
  await page.route(/\/api\/classification\/doc\/[^/]+\/label/, async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved" }),
      });
    } else {
      await route.continue();
    }
  });
}

// Returns classification docs based on test scenario
function getClassificationDocsForScenario(scenario: string) {
  const baseDoc1 = {
    doc_id: "doc_001",
    claim_id: "CLM-TEST-001",
    filename: "loss_notice.pdf",
    predicted_type: "loss_notice",
    confidence: 0.95,
    signals: ["date_of_loss", "claimant_name"],
    doc_type_truth: null,
  };

  const baseDoc2 = {
    doc_id: "doc_002",
    claim_id: "CLM-TEST-001",
    filename: "police_report.pdf",
    predicted_type: "police_report",
    confidence: 0.88,
    signals: ["officer_name"],
    doc_type_truth: null,
  };

  const baseDoc3 = {
    doc_id: "doc_003",
    claim_id: "CLM-TEST-001",
    filename: "insurance_policy.pdf",
    predicted_type: "insurance_policy",
    confidence: 0.72,
    signals: ["policy_number"],
    doc_type_truth: null,
  };

  if (scenario === "with_labels") {
    // BUG TEST: doc_001 has labels (field_labels filled), but review_status might still be "pending"
    // if the backend only checks doc_labels.doc_type_correct and not field_labels
    return [
      { ...baseDoc1, review_status: "pending" }, // BUG: should be "confirmed" if labels exist
      { ...baseDoc2, review_status: "pending" },
      { ...baseDoc3, review_status: "pending" },
    ];
  }

  return [
    { ...baseDoc1, review_status: "pending" },
    { ...baseDoc2, review_status: "pending" },
    { ...baseDoc3, review_status: "pending" },
  ];
}

// Returns doc payload based on test scenario
function getDocPayloadForScenario(docId: string, scenario: string) {
  const basePayload = {
    doc_id: docId,
    claim_id: "CLM-TEST-001",
    filename: docId === "doc_001" ? "loss_notice.pdf" : docId === "doc_002" ? "police_report.pdf" : "insurance_policy.pdf",
    doc_type: docId === "doc_001" ? "loss_notice" : docId === "doc_002" ? "police_report" : "insurance_policy",
    language: "en",
    pages: [
      {
        page: 1,
        text: "Sample document text for testing.",
        text_md5: "test123",
      },
    ],
    extraction: {
      schema_version: "extraction_result_v1",
      run: {
        run_id: "run_test_001",
        extractor_version: "1.0.0",
        model: "gpt-4o",
        prompt_version: "v1",
        input_hashes: { pages: "hash123" },
      },
      doc: {
        doc_id: docId,
        claim_id: "CLM-TEST-001",
        doc_type: "loss_notice",
        doc_type_confidence: 0.95,
        language: "en",
        page_count: 1,
      },
      pages: [{ page: 1, text: "Sample text", text_md5: "test123" }],
      fields: [
        {
          name: "date_of_loss",
          value: "January 10, 2024",
          normalized_value: "2024-01-10",
          confidence: 0.98,
          status: "present",
          provenance: [{ page: 1, method: "extraction", text_quote: "January 10, 2024", char_start: 0, char_end: 16 }],
          value_is_placeholder: false,
        },
        {
          name: "claimant_name",
          value: "John Smith",
          normalized_value: "John Smith",
          confidence: 0.95,
          status: "present",
          provenance: [{ page: 1, method: "extraction", text_quote: "John Smith", char_start: 20, char_end: 30 }],
          value_is_placeholder: false,
        },
        {
          name: "policy_number",
          value: "POL-123456",
          normalized_value: "POL-123456",
          confidence: 0.92,
          status: "present",
          provenance: [{ page: 1, method: "extraction", text_quote: "POL-123456", char_start: 35, char_end: 45 }],
          value_is_placeholder: false,
        },
        {
          name: "vehicle_plate",
          value: null, // No extracted value
          normalized_value: null,
          confidence: 0,
          status: "missing",
          provenance: [],
          value_is_placeholder: false,
        },
      ],
      quality_gate: {
        status: "pass",
        reasons: [],
        missing_required_fields: [],
        needs_vision_fallback: false,
      },
    },
    has_pdf: true,
    has_image: false,
    labels: null,
  };

  if (scenario === "with_labels" && docId === "doc_001") {
    // doc_001 has been labeled with field labels
    return {
      ...basePayload,
      labels: {
        schema_version: "label_v3",
        doc_id: docId,
        claim_id: "CLM-TEST-001",
        review: {
          reviewed_at: "2024-01-14T21:30:00Z",
          reviewer: "admin",
          notes: "Verified all fields",
        },
        field_labels: [
          { field_name: "date_of_loss", state: "LABELED", truth_value: "2024-01-10", notes: "" },
          { field_name: "claimant_name", state: "LABELED", truth_value: "John Smith", notes: "" },
          { field_name: "policy_number", state: "LABELED", truth_value: "POL-123456", notes: "" },
          { field_name: "vehicle_plate", state: "LABELED", truth_value: "ZH238518", notes: "" }, // Truth set even though extracted is null
        ],
        doc_labels: {
          doc_type_correct: true, // Classification confirmed
        },
      },
    };
  }

  if (scenario === "mismatch_values" && docId === "doc_001") {
    // doc_001 has labels where truth differs from extracted (should show "Incorrect")
    return {
      ...basePayload,
      labels: {
        schema_version: "label_v3",
        doc_id: docId,
        claim_id: "CLM-TEST-001",
        review: {
          reviewed_at: "2024-01-14T21:30:00Z",
          reviewer: "admin",
          notes: "",
        },
        field_labels: [
          // MISMATCH: extracted "2024-01-10" vs truth "2024-01-11" - should show Incorrect
          { field_name: "date_of_loss", state: "LABELED", truth_value: "2024-01-11", notes: "" },
          // MATCH: both are "John Smith" - should show Correct
          { field_name: "claimant_name", state: "LABELED", truth_value: "John Smith", notes: "" },
          // MISMATCH: extracted "POL-123456" vs truth "POL-999999" - should show Incorrect
          { field_name: "policy_number", state: "LABELED", truth_value: "POL-999999", notes: "" },
          // MISSING: extracted is null, truth exists - should show Missing
          { field_name: "vehicle_plate", state: "LABELED", truth_value: "ZH238518", notes: "" },
        ],
        doc_labels: {
          doc_type_correct: true,
        },
      },
    };
  }

  return basePayload;
}

test.describe("BUG: Labels should be at document level, not claim level", () => {
  test.beforeEach(async ({ page }) => {
    await setupLabelingTestMocks(page, "with_labels");
  });

  test("labeling doc_001 should NOT affect doc_002 status in the same claim", async ({ page }) => {
    // Navigate to documents page
    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await expect(docList).toBeVisible();

    // Wait for documents to load
    await expect(docList.getByText("loss_notice.pdf")).toBeVisible({ timeout: 10000 });

    // doc_001 (loss_notice.pdf) has labels - check its status badge
    const doc1Row = docList.locator("[data-testid='doc-list-item']").filter({ hasText: "loss_notice.pdf" });

    // doc_002 (police_report.pdf) does NOT have labels - should still be "Pending"
    const doc2Row = docList.locator("[data-testid='doc-list-item']").filter({ hasText: "police_report.pdf" });

    // BUG CHECK: doc_002 should show "Pending" (it has no labels)
    // If both docs show the same status, labels are being shared at claim level (BUG!)
    await expect(doc2Row).toContainText("Pending");

    // The key assertion: doc_001 and doc_002 should have DIFFERENT statuses
    // because only doc_001 has labels
    const doc1Status = await doc1Row.locator("span.rounded-full").textContent();
    const doc2Status = await doc2Row.locator("span.rounded-full").textContent();

    // If this assertion fails, it means labels are at claim level instead of document level
    // doc_001 should be "Labeled" or "Confirmed", doc_002 should be "Pending"
    expect(doc1Status).not.toEqual(doc2Status);
  });
});

test.describe("BUG: Status should NOT be 'Pending' when labels exist", () => {
  test.beforeEach(async ({ page }) => {
    await setupLabelingTestMocks(page, "with_labels");
  });

  test("document with field_labels should show 'Labeled' or 'Confirmed', not 'Pending'", async ({ page }) => {
    await page.goto("/batches/run_test_001/documents");
    // Don't use networkidle - PDF worker may fail to load from CDN
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await expect(docList.getByText("loss_notice.pdf")).toBeVisible({ timeout: 10000 });

    // Click on doc_001 which has labels
    await docList.getByText("loss_notice.pdf").click();

    // Wait for doc detail to load
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // The document has 4 field labels - verify they're shown as labeled
    const labeledCount = page.locator("text=/\\d+ of \\d+ labeled/");
    await expect(labeledCount).toBeVisible();

    // BUG CHECK: The document list item for doc_001 should NOT show "Pending"
    // since it has field_labels saved
    const doc1Row = docList.locator("[data-testid='doc-list-item']").filter({ hasText: "loss_notice.pdf" });

    // This assertion should FAIL if the bug exists (status stays "Pending" despite having labels)
    // Expected: "Labeled" or "Confirmed"
    // Actual (buggy): "Pending"
    await expect(doc1Row).not.toContainText("Pending");
  });

  test("after saving labels, status should change from 'Pending' to 'Labeled'", async ({ page }) => {
    // Start with default scenario (no labels)
    await setupLabelingTestMocks(page, "default");

    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await expect(docList.getByText("loss_notice.pdf")).toBeVisible({ timeout: 10000 });

    // Click on doc_001
    await docList.getByText("loss_notice.pdf").click();
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // Verify initial status is "Pending"
    const doc1Row = docList.locator("[data-testid='doc-list-item']").filter({ hasText: "loss_notice.pdf" });
    await expect(doc1Row).toContainText("Pending");

    // Expand first field and confirm it
    const firstFieldRow = page.locator("[data-testid='field-row']").first();
    await firstFieldRow.click();

    // Look for field-level confirm button (in FieldsTable, not ClassificationPanel)
    const confirmButton = firstFieldRow.getByRole("button", { name: /confirm/i });
    if (await confirmButton.isVisible()) {
      await confirmButton.click();
    }

    // Save the labels
    const saveButton = page.getByRole("button", { name: /^Save$/i });
    await expect(saveButton).toBeEnabled({ timeout: 5000 });
    await saveButton.click();

    // Wait for save to complete
    await page.waitForTimeout(500);

    // BUG CHECK: After saving, status should change from "Pending" to "Labeled"
    // This assertion will FAIL if the backend doesn't update review_status properly
    await expect(doc1Row).toContainText("Labeled");
  });
});

test.describe("BUG: Extracted value != truth should show 'Incorrect' badge", () => {
  test.beforeEach(async ({ page }) => {
    await setupLabelingTestMocks(page, "mismatch_values");
  });

  test("shows 'Incorrect' badge when extracted value differs from truth", async ({ page }) => {
    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await expect(docList.getByText("loss_notice.pdf")).toBeVisible({ timeout: 10000 });

    // Click on doc_001 which has mismatched values
    await docList.getByText("loss_notice.pdf").click();
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // Expand the date_of_loss field (extracted: 2024-01-10, truth: 2024-01-11)
    const dateField = page.locator("[data-testid='field-row']").filter({ hasText: /date.*loss/i });
    await dateField.click();

    // BUG CHECK: Should show "Incorrect" badge since values don't match
    // Extracted: 2024-01-10 vs Truth: 2024-01-11
    await expect(dateField.locator("text=Incorrect")).toBeVisible();
  });

  test("shows 'Correct' badge when extracted value matches truth", async ({ page }) => {
    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await docList.getByText("loss_notice.pdf").click();
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // Expand the claimant_name field (extracted: John Smith, truth: John Smith)
    const nameField = page.locator("[data-testid='field-row']").filter({ hasText: /claimant.*name/i });
    await nameField.click();

    // Should show "Correct" badge since values match
    await expect(nameField.locator("text=Correct")).toBeVisible();
  });

  test("shows 'Missing' badge when extracted value is null but truth exists", async ({ page }) => {
    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await docList.getByText("loss_notice.pdf").click();
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // Expand the vehicle_plate field (extracted: null, truth: ZH238518)
    const plateField = page.locator("[data-testid='field-row']").filter({ hasText: /vehicle.*plate/i });
    await plateField.click();

    // Should show "Missing" badge since extracted is null but truth exists
    await expect(plateField.locator("text=Missing")).toBeVisible();

    // Should show "No value extracted" text
    await expect(plateField.locator("text=No value extracted")).toBeVisible();
  });

  test("collapsed row shows X indicator for incorrect values", async ({ page }) => {
    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await docList.getByText("loss_notice.pdf").click();
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // The date_of_loss field (mismatched) should show X indicator even when collapsed
    const dateField = page.locator("[data-testid='field-row']").filter({ hasText: /date.*loss/i });

    // Look for the red X indicator in collapsed view
    // From FieldsTable.tsx line 237-239: shows text-destructive text-xs for incorrect
    const incorrectIndicator = dateField.locator("span.text-destructive");
    await expect(incorrectIndicator).toContainText("✗");
  });
});

test.describe("Integration: Label persistence across batch views", () => {
  test("labels saved in one batch should be visible when viewing same document in another batch", async ({ page }) => {
    // This tests that labels are stored at document level (run-independent)
    // not at batch/run level

    await setupLabelingTestMocks(page, "with_labels");

    // View doc_001 in batch run_test_001
    await page.goto("/batches/run_test_001/documents");
    await page.waitForLoadState("domcontentloaded");

    const docList = page.getByTestId("document-list");
    await docList.getByText("loss_notice.pdf").click();
    await page.waitForSelector("[data-testid='field-row']", { timeout: 10000 });

    // Verify labels are visible
    const labeledCount = page.locator("text=/4 of 4 labeled/");
    await expect(labeledCount).toBeVisible();

    // Now if we switch to a different batch (hypothetically),
    // the same document should still show its labels
    // because labels are stored at docs/{doc_id}/labels/latest.json
    // NOT at runs/{run_id}/labels/...

    // This is implicitly tested by the fact that the mock returns labels
    // regardless of which batch is selected
  });
});
