import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageViewer } from "../PageViewer";

describe("PageViewer", () => {
  test("highlights text using character offsets", () => {
    render(
      <PageViewer
        pages={[{ page: 1, text: "Policy Number: PN123", text_md5: "md5" }]}
        highlightQuote="PN123"
        highlightPage={1}
        highlightCharStart={15}
        highlightCharEnd={20}
      />
    );

    const marker = screen.getByTestId("highlight-marker");
    expect(marker).toHaveTextContent("PN123");
  });
});
