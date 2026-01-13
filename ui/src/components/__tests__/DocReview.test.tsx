import { describe, expect, test, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DocReview } from "../DocReview";
import type { DocPayload } from "../../types";

vi.mock("../../api/client", () => ({
  getDoc: vi.fn(),
  saveLabels: vi.fn(),
}));

vi.mock("../PageViewer", () => ({
  PageViewer: () => <div data-testid="page-viewer" />,
}));

vi.mock("../FieldsTable", () => ({
  FieldsTable: () => <div data-testid="fields-table" />,
}));

const { getDoc, saveLabels } = await import("../../api/client");

describe("DocReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  test("loads document and saves labels", async () => {
    const user = userEvent.setup();
    const payload: DocPayload = {
      doc_id: "doc_1",
      claim_id: "claim_1",
      filename: "doc.pdf",
      doc_type: "invoice",
      language: "en",
      pages: [{ page: 1, text: "Hello", text_md5: "abc" }],
      extraction: {
        schema_version: "extraction_result_v1",
        run: {
          run_id: "run_1",
          extractor_version: "v1",
          model: "gpt",
          prompt_version: "p1",
          input_hashes: {},
        },
        doc: {
          doc_id: "doc_1",
          claim_id: "claim_1",
          doc_type: "invoice",
          doc_type_confidence: 0.9,
          language: "en",
          page_count: 1,
        },
        pages: [],
        fields: [
          {
            name: "policy_number",
            value: "PN123",
            normalized_value: "PN123",
            confidence: 0.9,
            status: "present",
            provenance: [],
            value_is_placeholder: false,
          },
        ],
        quality_gate: {
          status: "pass",
          reasons: [],
          missing_required_fields: [],
        },
      },
      labels: null,
      has_pdf: true,
      has_image: false,
    };

    (getDoc as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(payload);
    (saveLabels as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ status: "saved" });

    const onSaved = vi.fn();

    render(<DocReview docId="doc_1" onBack={vi.fn()} onSaved={onSaved} />);

    await waitFor(() => {
      expect(getDoc).toHaveBeenCalled();
    });

    await user.type(screen.getByPlaceholderText("Reviewer name"), "QA User");
    await user.click(screen.getByRole("button", { name: /save review/i }));

    await waitFor(() => {
      expect(saveLabels).toHaveBeenCalledWith(
        "doc_1",
        "QA User",
        "",
        expect.any(Array),
        { doc_type_correct: true }
      );
    });
    expect(onSaved).toHaveBeenCalled();
  });
});
