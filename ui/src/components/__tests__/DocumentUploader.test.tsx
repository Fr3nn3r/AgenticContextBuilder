import { describe, expect, test, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DocumentUploader } from "../DocumentUploader";

function getDropZone() {
  return document.querySelector('.border-dashed') as HTMLElement;
}

function createDataTransfer(files: File[]) {
  // Just use a plain array - the component's validateFiles uses Array.from() which works with arrays
  return {
    files: files,
    items: files.map(file => ({
      kind: 'file',
      type: file.type,
      getAsFile: () => file,
    })),
    types: ['Files'],
  };
}

describe("DocumentUploader", () => {
  test("shows error for invalid file type via drag-drop", async () => {
    const onUpload = vi.fn();

    render(<DocumentUploader onUpload={onUpload} />);

    const badFile = new File([new Uint8Array([1, 2, 3])], "virus.exe", {
      type: "application/octet-stream",
    });

    const dropZone = getDropZone();
    fireEvent.drop(dropZone, { dataTransfer: createDataTransfer([badFile]) });

    await waitFor(() => {
      expect(
        screen.getByText(/Invalid type\. Allowed: \.pdf, \.png, \.jpg, \.jpeg, \.txt/i)
      ).toBeInTheDocument();
    });
    expect(onUpload).not.toHaveBeenCalled();
  });

  test("shows error for file over size limit via drag-drop", async () => {
    const onUpload = vi.fn();

    render(<DocumentUploader onUpload={onUpload} />);

    const bigFile = new File([new Uint8Array([1, 2, 3])], "big.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(bigFile, "size", { value: 101 * 1024 * 1024 });

    const dropZone = getDropZone();
    fireEvent.drop(dropZone, { dataTransfer: createDataTransfer([bigFile]) });

    await waitFor(() => {
      expect(screen.getByText(/File too large\. Max: 100MB/i)).toBeInTheDocument();
    });
    expect(onUpload).not.toHaveBeenCalled();
  });

  test("shows no errors for valid files only", async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);

    render(<DocumentUploader onUpload={onUpload} />);

    const goodFile = new File([new Uint8Array([1, 2, 3])], "loss_notice.pdf", {
      type: "application/pdf",
    });

    const dropZone = getDropZone();
    fireEvent.drop(dropZone, { dataTransfer: createDataTransfer([goodFile]) });

    // Wait for any async state updates
    await waitFor(() => {
      // Should NOT show any error messages for valid files
      expect(screen.queryByText(/Invalid type/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/File too large/i)).not.toBeInTheDocument();
    });
  });
});
