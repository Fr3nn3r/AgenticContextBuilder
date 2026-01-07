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
  isLoaded: () => boolean;
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

    // Function to normalize to alphanumeric only (strips punctuation like hyphens)
    const normalizeAlphanumeric = (text: string): string => {
      return text.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
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

      // Tier 2.5: Alphanumeric-only matching
      // Handles cases where punctuation (hyphens, slashes) breaks matching
      // e.g., "24-02-VH-7053819" matches even if split as "24-02-VH" + "-7053819"
      if (matchIndex === -1) {
        const searchAlphaNum = normalizeAlphanumeric(cleanedSearch);
        const fullTextAlphaNum = normalizeAlphanumeric(fullText);

        if (searchAlphaNum.length >= 4) {
          const alphaNumIndex = fullTextAlphaNum.indexOf(searchAlphaNum);
          if (alphaNumIndex !== -1) {
            // Map back to original text position
            let origPos = 0;
            let alphaPos = 0;
            while (alphaPos < alphaNumIndex && origPos < fullText.length) {
              if (/[a-zA-Z0-9]/.test(fullText[origPos])) {
                alphaPos++;
              }
              origPos++;
            }
            matchIndex = origPos;
            // Find end position
            const endAlphaPos = alphaPos + searchAlphaNum.length;
            while (alphaPos < endAlphaPos && origPos < fullText.length) {
              if (/[a-zA-Z0-9]/.test(fullText[origPos])) {
                alphaPos++;
              }
              origPos++;
            }
            matchLength = origPos - matchIndex;
          }
        }
      }

      // Tier 3: Significant substrings
      if (matchIndex === -1) {
        // Try to find the longest significant word/number sequence
        const significantParts = normalizedSearch
          .split(/[\s:,;]+/)
          .filter(p => p.length >= 3)  // Lowered from 4 to catch shorter values
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

      // Tier 3.5: Number-sequence matching for dates, policy numbers, IDs
      if (matchIndex === -1) {
        const numberSequences = cleanedSearch.match(/\d{3,}/g);  // 3+ digit sequences
        if (numberSequences) {
          // Sort by length (longest first) for best match
          for (const numSeq of numberSequences.sort((a, b) => b.length - a.length)) {
            const seqIndex = fullText.indexOf(numSeq);
            if (seqIndex !== -1) {
              matchIndex = seqIndex;
              matchLength = numSeq.length;
              break;
            }
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
        // Use semi-transparent background and outline so text underneath remains visible
        mark.style.cssText = "background-color: rgba(250, 204, 21, 0.4); color: inherit; padding: 2px 0; border-radius: 2px; outline: 2px solid rgba(250, 204, 21, 0.8); outline-offset: 1px;";
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
        if (numPages > 0 && page >= 1 && page <= numPages) {
          if (page === pageNumber) {
            // Already on this page - force highlight refresh via state toggle
            setPageRendered(false);
            setTimeout(() => setPageRendered(true), 50);
          } else {
            setPageRendered(false);  // Reset to trigger highlight on new page
            setPageNumber(page);
          }
        }
      },
      highlightText: (text: string) => {
        setHighlightQuery(text);
      },
      isLoaded: () => numPages > 0,
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

    // Set initial page from prop only once when document loads
    // NOTE: We intentionally do NOT continuously sync currentPage prop to state
    // because that would overwrite ref-based navigation (goToPage calls from parent)
    useEffect(() => {
      if (currentPage && currentPage >= 1 && numPages > 0 && pageNumber === 1) {
        // Only set initial page if we're still on page 1 (not navigated yet)
        setPageNumber(currentPage);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [numPages]);  // Only trigger when document finishes loading

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
