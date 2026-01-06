import { useState, useEffect, forwardRef, useImperativeHandle } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import { cn } from "../lib/utils";

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export interface PDFViewerHandle {
  goToPage: (page: number) => void;
}

interface PDFViewerProps {
  url: string;
  currentPage?: number;
}

export const PDFViewer = forwardRef<PDFViewerHandle, PDFViewerProps>(
  function PDFViewer({ url, currentPage }, ref) {
    const [numPages, setNumPages] = useState<number>(0);
    const [pageNumber, setPageNumber] = useState<number>(currentPage || 1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [containerWidth, setContainerWidth] = useState<number>(600);

    // Expose goToPage method via ref
    useImperativeHandle(ref, () => ({
      goToPage: (page: number) => {
        if (page >= 1 && page <= numPages) {
          setPageNumber(page);
        } else if (page >= 1) {
          // If numPages not loaded yet, still set the page
          setPageNumber(page);
        }
      },
    }));

    // Navigate to highlighted page when it changes
    useEffect(() => {
      if (currentPage && currentPage >= 1 && currentPage <= numPages) {
        setPageNumber(currentPage);
      }
    }, [currentPage, numPages]);

    // Measure container width for responsive PDF scaling
    useEffect(() => {
      const updateWidth = () => {
        const container = document.getElementById("pdf-container");
        if (container) {
          // Leave some padding
          setContainerWidth(container.clientWidth - 32);
        }
      };

      updateWidth();
      window.addEventListener("resize", updateWidth);
      return () => window.removeEventListener("resize", updateWidth);
    }, []);

    function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
      setNumPages(numPages);
      setLoading(false);
      // Navigate to highlighted page if specified
      if (currentPage && currentPage <= numPages) {
        setPageNumber(currentPage);
      }
    }

    function onDocumentLoadError(err: Error) {
      setError(err.message);
      setLoading(false);
    }

    function goToPrevPage() {
      setPageNumber((prev) => Math.max(1, prev - 1));
    }

    function goToNextPage() {
      setPageNumber((prev) => Math.min(numPages, prev + 1));
    }

    return (
      <div id="pdf-container" className="flex flex-col h-full bg-gray-100">
        {/* Page navigation */}
        <div className="flex items-center justify-center gap-4 p-2 bg-white border-b">
          <button
            onClick={goToPrevPage}
            disabled={pageNumber <= 1}
            className={cn(
              "px-3 py-1 rounded text-sm",
              pageNumber <= 1
                ? "text-gray-300 cursor-not-allowed"
                : "text-gray-700 hover:bg-gray-100"
            )}
          >
            Previous
          </button>
          <span className="text-sm text-gray-600">
            Page {pageNumber} of {numPages || "?"}
          </span>
          <button
            onClick={goToNextPage}
            disabled={pageNumber >= numPages}
            className={cn(
              "px-3 py-1 rounded text-sm",
              pageNumber >= numPages
                ? "text-gray-300 cursor-not-allowed"
                : "text-gray-700 hover:bg-gray-100"
            )}
          >
            Next
          </button>
        </div>

        {/* PDF content */}
        <div className="flex-1 overflow-auto flex items-start justify-center p-4">
          {loading && !error && (
            <div className="text-gray-500 mt-8">Loading PDF...</div>
          )}

          {error && (
            <div className="text-red-600 mt-8">
              Failed to load PDF: {error}
            </div>
          )}

          <Document
            file={url}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading=""
            error=""
            className="shadow-lg"
          >
            <Page
              pageNumber={pageNumber}
              renderTextLayer={true}
              renderAnnotationLayer={true}
              className="bg-white"
              width={containerWidth}
            />
          </Document>
        </div>
      </div>
    );
  }
);
