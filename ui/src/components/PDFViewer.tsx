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

    // Function to clean evidence text (strip HTML tags, normalize whitespace)
    const cleanEvidenceText = (text: string): string => {
      // Remove HTML/XML tags like <td>, </td>, etc.
      let cleaned = text.replace(/<[^>]*>/g, "");
      // Remove common artifacts
      cleaned = cleaned.replace(/&lt;/g, "<").replace(/&gt;/g, ">");
      cleaned = cleaned.replace(/&amp;/g, "&");
      // Normalize whitespace
      cleaned = cleaned.replace(/\s+/g, " ").trim();
      return cleaned;
    };

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

      // Clean and normalize search text (strip HTML tags, etc.)
      const cleanedSearch = cleanEvidenceText(searchText);
      const normalizedSearch = cleanedSearch.toLowerCase().trim();
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

      // Normalize PDF text for comparison (collapse whitespace)
      const normalizedFullText = fullText.toLowerCase().replace(/\s+/g, " ");

      // Also create a version of search without spaces for flexible matching
      const searchNoSpaces = normalizedSearch.replace(/\s+/g, "");
      const fullTextNoSpaces = fullText.toLowerCase().replace(/\s+/g, "");

      // Try exact match first
      let matchIndex = normalizedFullText.indexOf(normalizedSearch);
      let matchLength = normalizedSearch.length;

      // If no exact match, try without spaces (PDF often splits text oddly)
      if (matchIndex === -1 && searchNoSpaces.length >= 5) {
        const noSpaceIndex = fullTextNoSpaces.indexOf(searchNoSpaces);
        if (noSpaceIndex !== -1) {
          // Found match in no-space version, need to map back to original
          // Approximate: find the position in original text
          let origPos = 0;
          let noSpacePos = 0;
          while (noSpacePos < noSpaceIndex && origPos < fullText.length) {
            if (!/\s/.test(fullText[origPos])) {
              noSpacePos++;
            }
            origPos++;
          }
          matchIndex = origPos;
          // Find end position
          let endNoSpacePos = noSpacePos + searchNoSpaces.length;
          while (noSpacePos < endNoSpacePos && origPos < fullText.length) {
            if (!/\s/.test(fullText[origPos])) {
              noSpacePos++;
            }
            origPos++;
          }
          matchLength = origPos - matchIndex;
        }
      }

      // If still no match, try finding significant substrings
      if (matchIndex === -1) {
        // Try to find the longest significant word/number sequence
        const significantParts = normalizedSearch
          .split(/[\s:,;]+/)
          .filter(p => p.length >= 4)
          .sort((a, b) => b.length - a.length); // Longest first

        for (const part of significantParts) {
          const partIndex = normalizedFullText.indexOf(part);
          if (partIndex !== -1) {
            matchIndex = partIndex;
            matchLength = part.length;
            break;
          }
        }
      }

      if (matchIndex === -1) return;

      highlightRange(charMap, matchIndex, matchIndex + matchLength);
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
