import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BatchSelector } from "../BatchSelector";

describe("BatchSelector", () => {
  test("calls onBatchChange when selection changes", async () => {
    const user = userEvent.setup();
    const onBatchChange = vi.fn();
    const batches = [
      { batch_id: "batch_1", timestamp: "2024-01-01T12:00:00Z" },
      { batch_id: "batch_2", timestamp: "2024-02-01T12:00:00Z" },
    ];

    render(
      <BatchSelector
        batches={batches}
        selectedBatchId="batch_1"
        onBatchChange={onBatchChange}
      />
    );

    await user.selectOptions(screen.getByRole("combobox"), "batch_2");

    expect(onBatchChange).toHaveBeenCalledWith("batch_2");
  });

  test("sorts batches descending (most recent first)", () => {
    const onBatchChange = vi.fn();
    const batches = [
      { batch_id: "batch_z", timestamp: "2024-01-01T12:00:00Z" },
      { batch_id: "batch_a", timestamp: "2024-02-01T12:00:00Z" },
    ];

    render(
      <BatchSelector
        batches={batches}
        selectedBatchId="batch_a"
        onBatchChange={onBatchChange}
        testId="sort-test-selector"
      />
    );

    const select = screen.getByTestId("sort-test-selector");
    const options = select.querySelectorAll("option");
    // Descending order: z comes before a
    expect(options[0]).toHaveValue("batch_z");
    expect(options[1]).toHaveValue("batch_a");
  });
});
