import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { getDoc, listClaims, saveLabels } from "../client";

describe("api client", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("listClaims builds run filter query", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [],
    } as unknown as Response);

    await listClaims("run_123");

    expect(fetchMock).toHaveBeenCalledWith("/api/claims?run_id=run_123", undefined);
  });

  test("getDoc builds query params", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ doc_id: "doc_1" }),
    } as unknown as Response);

    await getDoc("doc_1", "claim_1", "run_1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/docs/doc_1?claim_id=claim_1&run_id=run_1",
      undefined
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

    expect(fetchMock).toHaveBeenCalledWith("/api/docs/doc_1/labels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reviewer: "Reviewer",
        notes: "notes",
        field_labels: [],
        doc_labels: { doc_type_correct: true },
      }),
    });
  });

  test("throws error when response not ok", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "Boom" }),
    } as unknown as Response);

    await expect(listClaims()).rejects.toThrow("Boom");
  });
});
