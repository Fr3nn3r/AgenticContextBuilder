import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import {
  getDoc,
  listClaims,
  listDocs,
  saveLabels,
  getInsightsExamples,
  getInsightsFieldDetails,
  compareRuns,
  startPipeline,
  getPipelineStatus,
  listPipelineBatches,
  getAzureDI,
  // Compliance API functions
  verifyDecisionLedger,
  listDecisions,
  listVersionBundles,
  getVersionBundle,
  getConfigHistory,
  getTruthHistory,
  getLabelHistory,
} from "../client";

describe("api client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ============================================================================
  // Existing Tests
  // ============================================================================

  test("listClaims builds run filter query", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response);

    await listClaims("run_123");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/claims?run_id=run_123",
      expect.objectContaining({ headers: expect.any(Headers) })
    );
  });

  test("getDoc builds query params", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ doc_id: "doc_1" }),
    } as unknown as Response);

    await getDoc("doc_1", "claim_1", "run_1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/docs/doc_1?claim_id=claim_1&run_id=run_1",
      expect.objectContaining({ headers: expect.any(Headers) })
    );
  });

  test("saveLabels posts payload", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ status: "saved" }),
    } as unknown as Response);

    await saveLabels(
      "doc_1",
      "Reviewer",
      "notes",
      [],
      { doc_type_correct: true }
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/docs/doc_1/labels",
      expect.objectContaining({
        method: "POST",
        headers: expect.any(Headers),
        body: JSON.stringify({
          reviewer: "Reviewer",
          notes: "notes",
          field_labels: [],
          doc_labels: { doc_type_correct: true },
        }),
      })
    );
  });

  test("throws error when response not ok", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Boom" }),
    } as unknown as Response);

    await expect(listClaims()).rejects.toThrow("Boom");
  });

  // ============================================================================
  // Query Parameter Building Tests
  // ============================================================================

  describe("query parameter building", () => {
    test("listDocs includes runId param when provided", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await listDocs("claim_123", "run_456");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/claims/claim_123/docs?run_id=run_456",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("listDocs omits runId when not provided", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await listDocs("claim_123");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/claims/claim_123/docs",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("getInsightsExamples includes all optional params", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await getInsightsExamples({
        doc_type: "invoice",
        field: "total_amount",
        outcome: "mismatch",
        run_id: "run_123",
        limit: 20,
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/insights/examples?doc_type=invoice&field=total_amount&outcome=mismatch&run_id=run_123&limit=20",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("getInsightsExamples omits undefined params", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await getInsightsExamples({
        doc_type: "invoice",
      });

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/insights/examples?doc_type=invoice",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("getInsightsFieldDetails encodes special characters", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as unknown as Response);

      await getInsightsFieldDetails("doc type/special", "field&name", "run=1");

      const call = fetchMock.mock.calls[0][0] as string;
      expect(call).toContain("doc_type=doc+type%2Fspecial");
      expect(call).toContain("field=field%26name");
      expect(call).toContain("run_id=run%3D1");
    });

    test("compareRuns builds baseline and current params", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as unknown as Response);

      await compareRuns("baseline_001", "current_002");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/insights/compare?baseline=baseline_001&current=current_002",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });
  });

  // ============================================================================
  // Response Mapping Tests (run_id -> batch_id)
  // ============================================================================

  describe("response mapping", () => {
    test("startPipeline maps run_id to batch_id", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ run_id: "run_abc", status: "started" }),
      } as unknown as Response);

      const result = await startPipeline(["claim_1"], "gpt-4o");

      expect(result).toEqual({ batch_id: "run_abc", status: "started" });
    });

    test("getPipelineStatus maps run_id to batch_id", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          run_id: "run_xyz",
          status: "completed",
          claim_ids: ["claim_1"],
        }),
      } as unknown as Response);

      const result = await getPipelineStatus("run_xyz");

      expect(result.batch_id).toBe("run_xyz");
      expect(result.status).toBe("completed");
    });

    test("listPipelineBatches maps all run_id to batch_id", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [
          { run_id: "run_1", status: "completed", claim_ids: [] },
          { run_id: "run_2", status: "running", claim_ids: [] },
        ],
      } as unknown as Response);

      const results = await listPipelineBatches();

      expect(results).toHaveLength(2);
      expect(results[0].batch_id).toBe("run_1");
      expect(results[1].batch_id).toBe("run_2");
    });
  });

  // ============================================================================
  // Error Handling Tests
  // ============================================================================

  describe("error handling", () => {
    test("throws generic error when json parse fails", async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("JSON parse error");
        },
      } as unknown as Response);

      await expect(listClaims()).rejects.toThrow("Unknown error");
    });

    test("throws HTTP status when no detail in error response", async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({}),
      } as unknown as Response);

      await expect(listClaims()).rejects.toThrow("HTTP 404");
    });
  });

  // ============================================================================
  // Azure DI Caching Tests
  // ============================================================================

  describe("getAzureDI caching", () => {
    test("returns null on 404 error", async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Not found" }),
      } as unknown as Response);

      const result = await getAzureDI("doc_new", "claim_new");

      expect(result).toBeNull();
    });

    test("returns cached value on subsequent calls", async () => {
      const mockData = { raw_azure_di_output: { pages: [], content: "" } };
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => mockData,
      } as unknown as Response);

      // First call
      const result1 = await getAzureDI("doc_cached", "claim_cached");
      expect(result1).toEqual(mockData);
      expect(fetchMock).toHaveBeenCalledTimes(1);

      // Second call - should use cache
      const result2 = await getAzureDI("doc_cached", "claim_cached");
      expect(result2).toEqual(mockData);
      expect(fetchMock).toHaveBeenCalledTimes(1); // Still 1, no new fetch
    });

    test("caches null to avoid repeated 404s", async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Not found" }),
      } as unknown as Response);

      // First call
      const result1 = await getAzureDI("doc_404", "claim_404");
      expect(result1).toBeNull();
      expect(fetchMock).toHaveBeenCalledTimes(1);

      // Second call - should return cached null
      const result2 = await getAzureDI("doc_404", "claim_404");
      expect(result2).toBeNull();
      expect(fetchMock).toHaveBeenCalledTimes(1); // Still 1, no new fetch
    });
  });

  // ============================================================================
  // Compliance API Tests
  // ============================================================================

  describe("compliance API", () => {
    test("verifyDecisionLedger calls correct endpoint", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ valid: true, total_records: 100 }),
      } as unknown as Response);

      const result = await verifyDecisionLedger();

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/ledger/verify",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
      expect(result.valid).toBe(true);
      expect(result.total_records).toBe(100);
    });

    test("listDecisions calls correct endpoint with no params", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await listDecisions();

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/ledger/decisions",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("listDecisions includes all filter params", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await listDecisions({
        decision_type: "classification",
        doc_id: "doc_123",
        claim_id: "claim_456",
        since: "2026-01-01T00:00:00Z",
        limit: 50,
      });

      const call = fetchMock.mock.calls[0][0] as string;
      expect(call).toContain("decision_type=classification");
      expect(call).toContain("doc_id=doc_123");
      expect(call).toContain("claim_id=claim_456");
      expect(call).toContain("since=2026-01-01T00%3A00%3A00Z");
      expect(call).toContain("limit=50");
    });

    test("listDecisions omits undefined params", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await listDecisions({ decision_type: "extraction" });

      const call = fetchMock.mock.calls[0][0] as string;
      expect(call).toContain("decision_type=extraction");
      expect(call).not.toContain("doc_id");
      expect(call).not.toContain("claim_id");
    });

    test("listVersionBundles calls correct endpoint", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [
          { run_id: "run_1", bundle_id: "vb_1", model_name: "gpt-4o" },
        ],
      } as unknown as Response);

      const result = await listVersionBundles();

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/version-bundles",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
      expect(result).toHaveLength(1);
      expect(result[0].run_id).toBe("run_1");
    });

    test("getVersionBundle calls correct endpoint with run_id", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          bundle_id: "vb_123",
          run_id: "run_abc",
          model_name: "gpt-4o",
          git_commit: "abc123",
        }),
      } as unknown as Response);

      const result = await getVersionBundle("run_abc");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/version-bundles/run_abc",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
      expect(result.bundle_id).toBe("vb_123");
      expect(result.git_commit).toBe("abc123");
    });

    test("getVersionBundle encodes special characters in run_id", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ bundle_id: "vb_1" }),
      } as unknown as Response);

      await getVersionBundle("run/with/slashes");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/version-bundles/run%2Fwith%2Fslashes",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("getConfigHistory calls correct endpoint", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [
          { timestamp: "2026-01-14T12:00:00Z", action: "create", config_id: "cfg_1" },
        ],
      } as unknown as Response);

      const result = await getConfigHistory();

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/config-history?limit=100",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
      expect(result).toHaveLength(1);
    });

    test("getConfigHistory accepts custom limit", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => [],
      } as unknown as Response);

      await getConfigHistory(50);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/config-history?limit=50",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });

    test("getTruthHistory calls correct endpoint", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          file_md5: "abc123",
          version_count: 3,
          versions: [],
        }),
      } as unknown as Response);

      const result = await getTruthHistory("abc123");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/truth-history/abc123",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
      expect(result.file_md5).toBe("abc123");
      expect(result.version_count).toBe(3);
    });

    test("getLabelHistory calls correct endpoint", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          doc_id: "DOC-001",
          version_count: 2,
          versions: [],
        }),
      } as unknown as Response);

      const result = await getLabelHistory("DOC-001");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/label-history/DOC-001",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
      expect(result.doc_id).toBe("DOC-001");
    });

    test("getLabelHistory encodes special characters", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ doc_id: "DOC/SPECIAL", version_count: 0, versions: [] }),
      } as unknown as Response);

      await getLabelHistory("DOC/SPECIAL");

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/compliance/label-history/DOC%2FSPECIAL",
        expect.objectContaining({ headers: expect.any(Headers) })
      );
    });
  });
});
