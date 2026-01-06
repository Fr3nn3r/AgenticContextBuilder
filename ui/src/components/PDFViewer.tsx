import { useState, useEffect, forwardRef, useImperativeHandle, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";
import { cn } from "../lib/utils";

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export interface PDFViewerHandle {
  goToPage: (page: number) => void;
  highlightText: (text: string) => void;
}

interface PDFViewerProps {
  url: string;
  currentPage?: number;
  highlightText?: string;
}

export const PDFViewer = forwardRef<PDFViewerHandle, PDFViewerProps>(
  function PDFViewer({ url, currentPage, highlightText: initialHighlight }, ref) {
    const [numPages, setNumPages] = useState<number>(0);
    const [pageNumber, setPageNumber] = useState<number>(currentPage || 1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [containerWidth, setContainerWidth] = useState<number>(600);
    const [highlightQuery, setHighlightQuery] = useState<string>(initialHighlight || "");
    const [pageRendered, setPageRendered] = useState(false);

    // Function to highlight text in the PDF text layer
    const applyHighlight = useCallback((searchText: string) => {
      if (!searchText) {
        // Clear existing highlights
        const existingHighlights = document.querySelectorAll(".pdf-text-highlight");
        existingHighlights.forEach((el) => {
          const parent = el.parentNode;
          if (parent) {
            parent.replaceChild(document.createTextNode(el.textContent || ""), el);
            parent.normalize();
          }
        });
        return;
      }

      // Find the text layer
      const textLayer = document.querySelector(".react-pdf__Page__textContent");
      if (!textLayer) return;

      // Clear previous highlights first
      const existingHighlights = textLayer.querySelectorAll(".pdf-text-highlight");
      existingHighlights.forEach((el) => {
        const parent = el.parentNode;
        if (parent) {
          parent.replaceChild(document.createTextNode(el.textContent || ""), el);
          parent.normalize();
        }
      });

      // Normalize search text for comparison
      const normalizedSearch = searchText.toLowerCase().trim();
      if (normalizedSearch.length < 3) return;

      // Get all text spans
      const spans = textLayer.querySelectorAll("span");

      // Build full text and map character positions to spans
      let fullText = "";
      const charMap: { span: Element; startIndex: number; endIndex: number }[] = [];

      spans.forEach((span) => {
        const text = span.textContent || "";
        charMap.push({
          span,
          startIndex: fullText.length,
          endIndex: fullText.length + text.length,
        });
        fullText += text;
      });

      // Search for the text (case-insensitive)
      const normalizedFullText = fullText.toLowerCase();
      const matchIndex = normalizedFullText.indexOf(normalizedSearch);

      if (matchIndex === -1) {
        // Try partial match with first significant words
        const words = normalizedSearch.split(/\s+/).filter(w => w.length > 2);
        if (words.length > 0) {
          const firstWord = words[0];
          const wordIndex = normalizedFullText.indexOf(firstWord);
          if (wordIndex !== -1) {
            highlightRange(charMap, wordIndex, wordIndex + firstWord.length);
          }
        }
        return;
      }

      highlightRange(charMap, matchIndex, matchIndex + normalizedSearch.length);
    }, []);

    // Helper to highlight a range of characters
    function highlightRange(
      charMap: { span: Element; startIndex: number; endIndex: number }[],
      start: number,
      end: number
    ) {
      // Find spans that contain the match
      const affectedSpans = charMap.filter(
        (item) => item.endIndex > start && item.startIndex < end
      );

      affectedSpans.forEach((item) => {
        const span = item.span;
        const text = span.textContent || "";

        // Calculate which part of this span to highlight
        const localStart = Math.max(0, start - item.startIndex);
        const localEnd = Math.min(text.length, end - item.startIndex);

        if (localStart >= localEnd) return;

        // Create highlighted version
        const before = text.slice(0, localStart);
        const highlighted = text.slice(localStart, localEnd);
        const after = text.slice(localEnd);

        // Clear span and add parts
        span.textContent = "";

        if (before) {
          span.appendChild(document.createTextNode(before));
        }

        const mark = document.createElement("mark");
        mark.className = "pdf-text-highlight";
        mark.style.cssText = "background-color: #fef08a; color: inherit; padding: 0; border-radius: 2px;";
        mark.textContent = highlighted;
        span.appendChild(mark);

        if (after) {
          span.appendChild(document.createTextNode(after));
        }
      });

      // Scroll to first highlight
      setTimeout(() => {
        const firstHighlight = document.querySelector(".pdf-text-highlight");
        if (firstHighlight) {
          firstHighlight.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 100);
    }

    // Expose methods via ref
    useImperativeHandle(ref, () => ({
      goToPage: (page: number) => {
        if (page >= 1 && page <= numPages) {
          setPageNumber(page);
        } else if (page >= 1) {
          setPageNumber(page);
        }
      },
      highlightText: (text: string) => {
        setHighlightQuery(text);
      },
    }));

    // Apply highlight when query or page changes
    useEffect(() => {
      if (pageRendered && highlightQuery) {
        // Small delay to ensure text layer is fully rendered
        const timer = setTimeout(() => {
          applyHighlight(highlightQuery);
        }, 200);
        return () => clearTimeout(timer);
      }
    }, [highlightQuery, pageRendered, pageNumber, applyHighlight]);

    // Update highlight when initial prop changes
    useEffect(() => {
      if (initialHighlight) {
        setHighlightQuery(initialHighlight);
      }
    }, [initialHighlight]);

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
      if (currentPage && currentPage <= numPages) {
        setPageNumber(currentPage);
      }
    }

    function onDocumentLoadError(err: Error) {
      setError(err.message);
      setLoading(false);
    }

    function onPageRenderSuccess() {
      setPageRendered(true);
    }

    function goToPrevPage() {
      setPageRendered(false);
      setPageNumber((prev) => Math.max(1, prev - 1));
    }

    function goToNextPage() {
      setPageRendered(false);
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
              onRenderSuccess={onPageRenderSuccess}
            />
          </Document>
        </div>
      </div>
    );
  }
);
