import { useState } from "react";
import type { PageContent } from "../types";
import { cn } from "../lib/utils";

interface PageViewerProps {
  pages: PageContent[];
  highlightQuote?: string;
  highlightPage?: number;
}

export function PageViewer({ pages, highlightQuote, highlightPage }: PageViewerProps) {
  const [selectedPage, setSelectedPage] = useState(highlightPage || 1);

  const currentPage = pages.find((p) => p.page === selectedPage);

  // Highlight text in page content
  function renderPageContent(text: string) {
    if (!highlightQuote || selectedPage !== highlightPage) {
      return <pre className="whitespace-pre-wrap text-sm">{text}</pre>;
    }

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
        <mark className="bg-yellow-200 px-0.5">{match}</mark>
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
