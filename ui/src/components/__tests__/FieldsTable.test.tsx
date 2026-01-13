import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FieldsTable } from "../FieldsTable";
import { makeExtractedField, makeFieldLabel } from "../../test/fixtures";

describe("FieldsTable", () => {
  test("calls onConfirm when confirming a value", async () => {
    const user = userEvent.setup();
    const field = makeExtractedField();
    const label = makeFieldLabel({ state: "UNLABELED" });
    const onConfirm = vi.fn();

    render(
      <FieldsTable
        fields={[field]}
        labels={[label]}
        onConfirm={onConfirm}
        onUnverifiable={vi.fn()}
        onEditTruth={vi.fn()}
        onQuoteClick={vi.fn()}
        docType="insurance_policy"
      />
    );

    await user.click(screen.getByText("Policy number"));
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(onConfirm).toHaveBeenCalledWith("policy_number", "PN123");
  });
});
