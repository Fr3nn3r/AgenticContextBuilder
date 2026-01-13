import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DocumentViewer } from "../DocumentViewer";

vi.mock("../PageViewer", () => ({
  PageViewer: () => <div data-testid="page-viewer" />,
}));

vi.mock("../PDFViewer", () => ({
  PDFViewer: vi.fn(() => <div data-testid="pdf-viewer" />),
}));

vi.mock("../ImageViewer", () => ({
  ImageViewer: () => <div data-testid="image-viewer" />,
}));

vi.mock("../../api/client", () => ({
  getAzureDI: vi.fn(),
}));

vi.mock("../../lib/bboxUtils", () => ({
  computeBoundingBoxes: vi.fn(() => []),
}));

describe("DocumentViewer", () => {
  test("defaults to PDF tab when available and allows switching to text", async () => {
    const user = userEvent.setup();
    render(
      <DocumentViewer
        pages={[{ page: 1, text: "Hello", text_md5: "md5" }]}
        sourceUrl="http://example.com/doc.pdf"
        hasPdf
      />
    );

    expect(screen.getByTestId("pdf-viewer")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Text" }));
    expect(screen.getByTestId("page-viewer")).toBeInTheDocument();
  });
});
