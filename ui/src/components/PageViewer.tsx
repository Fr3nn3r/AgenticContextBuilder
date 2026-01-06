import { useState, useEffect, useRef } from "react";
import type { PageContent } from "../types";
import { cn } from "../lib/utils";

interface PageViewerProps {
  pages: PageContent[];
  highlightQuote?: string;
  highlightPage?: number;
  highlightCharStart?: number;
  highlightCharEnd?: number;
}

export function PageViewer({
  pages,
  highlightQuote,
  highlightPage,
  highlightCharStart,
  highlightCharEnd,
}: PageViewerProps) {
  const [selectedPage, setSelectedPage] = useState(highlightPage || 1);
  const highlightRef = useRef<HTMLElement>(null);

  const currentPage = pages.find((p) => p.page === selectedPage);

  // Auto-switch to highlight page when it changes
  useEffect(() => {
    if (highlightPage && highlightPage !== selectedPage) {
      setSelectedPage(highlightPage);
    }
  }, [highlightPage]);

  // Scroll to highlight when it appears
  useEffect(() => {
    if (highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightCharStart, highlightCharEnd, highlightQuote, selectedPage]);

  // Highlight text in page content using exact offsets or fallback to quote search
  function renderPageContent(text: string) {
    if (!highlightQuote || selectedPage !== highlightPage) {
      return <pre className="whitespace-pre-wrap text-sm">{text}</pre>;
    }

    // Try to use exact character offsets first
    if (highlightCharStart !== undefined && highlightCharEnd !== undefined) {
      const before = text.slice(0, highlightCharStart);
      const match = text.slice(highlightCharStart, highlightCharEnd);
      const after = text.slice(highlightCharEnd);

      // Verify the match looks correct (at least partially matches the quote)
      if (match.length > 0) {
        return (
          <pre className="whitespace-pre-wrap text-sm">
            {before}
            <mark ref={highlightRef} data-testid="highlight-marker" className="bg-yellow-200 px-0.5 ring-2 ring-yellow-400">{match}</mark>
            {after}
          </pre>
        );
      }
    }

    // Fallback: search for the quote in the text
    const lowerText = text.toLowerCase();
    const lowerQuote = highlightQuote.toLowerCase();
    const index = lowerText.indexOf(lowerQuote);

    if (index === -1) {
      return <pre className="whitespace-pre-wrap text-sm">{text}</pre>;
    }

    const before = text.slice(0, index);
    const match = text.slice(index, index + highlightQuote.length);
    const after = text.slice(index + highlightQuote.length);

    return (
      <pre className="whitespace-pre-wrap text-sm">
        {before}
        <mark ref={highlightRef} data-testid="highlight-marker" className="bg-yellow-200 px-0.5 ring-2 ring-yellow-400">{match}</mark>
        {after}
      </pre>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Page selector */}
      <div className="flex items-center gap-2 p-2 border-b bg-secondary/30">
        <span className="text-sm text-muted-foreground">Page:</span>
        <div className="flex gap-1">
          {pages.map((page) => (
            <button
              key={page.page}
              onClick={() => setSelectedPage(page.page)}
              className={cn(
                "w-8 h-8 text-sm rounded transition-colors",
                selectedPage === page.page
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary hover:bg-secondary/80",
                highlightPage === page.page && selectedPage !== page.page
                  ? "ring-2 ring-yellow-400"
                  : ""
              )}
            >
              {page.page}
            </button>
          ))}
        </div>
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-auto p-4 bg-white">
        {currentPage ? (
          renderPageContent(currentPage.text)
        ) : (
          <div className="text-muted-foreground">No page content available</div>
        )}
      </div>
    </div>
  );
}
