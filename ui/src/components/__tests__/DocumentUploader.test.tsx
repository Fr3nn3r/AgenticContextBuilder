import { describe, expect, test, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DocumentUploader } from "../DocumentUploader";

function getFileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement;
}

describe("DocumentUploader", () => {
  test("shows error for invalid file type", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn();

    render(<DocumentUploader onUpload={onUpload} />);

    const badFile = new File([new Uint8Array([1, 2, 3])], "virus.exe", {
      type: "application/octet-stream",
    });

    await user.upload(getFileInput(), badFile);

    expect(
      screen.getByText(/Invalid type\. Allowed: \.pdf, \.png, \.jpg, \.jpeg, \.txt/i)
    ).toBeInTheDocument();
    expect(onUpload).not.toHaveBeenCalled();
  });

  test("shows error for file over size limit", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn();

    render(<DocumentUploader onUpload={onUpload} />);

    const bigFile = new File([new Uint8Array([1, 2, 3])], "big.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(bigFile, "size", { value: 101 * 1024 * 1024 });

    await user.upload(getFileInput(), bigFile);

    expect(screen.getByText(/File too large\. Max: 100MB/i)).toBeInTheDocument();
    expect(onUpload).not.toHaveBeenCalled();
  });

  test("calls onUpload for valid files", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn().mockResolvedValue(undefined);

    render(<DocumentUploader onUpload={onUpload} />);

    const goodFile = new File([new Uint8Array([1, 2, 3])], "loss_notice.pdf", {
      type: "application/pdf",
    });

    await user.upload(getFileInput(), goodFile);

    expect(onUpload).toHaveBeenCalledTimes(1);
    expect(onUpload).toHaveBeenCalledWith([goodFile]);
  });
});
