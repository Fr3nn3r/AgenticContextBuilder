import { useState, useEffect, useRef } from "react";
import type { PageContent, AzureDIOutput, BoundingBox } from "../types";
import { PageViewer } from "./PageViewer";
import { PDFViewer, PDFViewerHandle } from "./PDFViewer";
import { cn } from "../lib/utils";
import { getAzureDI } from "../api/client";
import { computeBoundingBoxes } from "../lib/bboxUtils";

type ViewerTab = "text" | "pdf" | "image" | "json";

interface DocumentViewerProps {
  pages: PageContent[];
  sourceUrl?: string;
  hasPdf?: boolean;
  hasImage?: boolean;
  extraction?: object | null;
  // Highlight props for text view
  highlightQuote?: string;
  highlightPage?: number;
  highlightCharStart?: number;
  highlightCharEnd?: number;
  // Extracted value to highlight in PDF (prioritized over quote)
  highlightValue?: string;
  // For Azure DI bbox highlighting
  claimId?: string;
  docId?: string;
}

export function DocumentViewer({
  pages,
  sourceUrl,
  hasPdf = false,
  hasImage = false,
  extraction,
  highlightQuote,
  highlightPage,
  highlightCharStart,
  highlightCharEnd,
  highlightValue,
  claimId,
  docId,
}: DocumentViewerProps) {
  // Default to PDF if available, otherwise text
  const defaultTab: ViewerTab = (hasPdf && sourceUrl) ? "pdf" : "text";
  const [activeTab, setActiveTab] = useState<ViewerTab>(defaultTab);
  const pdfViewerRef = useRef<PDFViewerHandle>(null);

  // Azure DI state for bbox highlighting
  const [azureDI, setAzureDI] = useState<AzureDIOutput | null>(null);
  const [azureDILoading, setAzureDILoading] = useState(false);
  const [highlightBboxes, setHighlightBboxes] = useState<BoundingBox[]>([]);

  // Update default tab when document changes
  useEffect(() => {
    const newDefault: ViewerTab = (hasPdf && sourceUrl) ? "pdf" : "text";
    setActiveTab(newDefault);
  }, [hasPdf, sourceUrl]);

  // Reset Azure DI when document changes
  useEffect(() => {
    setAzureDI(null);
    setHighlightBboxes([]);
  }, [docId]);

  // Lazy load Azure DI when highlight is triggered (for bbox highlighting)
  useEffect(() => {
    async function loadAzureDI() {
      if (!claimId || !docId) return;
      if (highlightPage === undefined) return;
      if (azureDI !== null || azureDILoading) return;

      setAzureDILoading(true);
      const data = await getAzureDI(docId, claimId);
      setAzureDI(data);
      setAzureDILoading(false);
    }

    loadAzureDI();
  }, [highlightPage, claimId, docId, azureDI, azureDILoading]);

  // Compute bounding boxes when Azure DI or highlight changes
  useEffect(() => {
    if (!azureDI || highlightPage === undefined) {
      setHighlightBboxes([]);
      return;
    }

    if (highlightCharStart !== undefined && highlightCharEnd !== undefined) {
      const bboxes = computeBoundingBoxes(
        azureDI,
        highlightPage,
        highlightCharStart,
        highlightCharEnd
      );
      setHighlightBboxes(bboxes);
    } else {
      setHighlightBboxes([]);
    }
  }, [azureDI, highlightPage, highlightCharStart, highlightCharEnd]);

  // When highlight changes (evidence clicked), navigate PDF to that page and highlight text
  useEffect(() => {
    if (highlightPage !== undefined && activeTab === "pdf" && pdfViewerRef.current) {
      const navigateAndHighlight = () => {
        if (!pdfViewerRef.current) return;

        // Check if PDF is loaded before navigating
        if (!pdfViewerRef.current.isLoaded()) {
          // PDF not loaded yet, retry after a delay
          setTimeout(navigateAndHighlight, 200);
          return;
        }

        pdfViewerRef.current.goToPage(highlightPage);
        // Prioritize highlighting the extracted value over the full quote
        const textToHighlight = highlightValue || highlightQuote;
        if (textToHighlight) {
          // Small delay to allow page navigation and render
          setTimeout(() => {
            pdfViewerRef.current?.highlightText(textToHighlight);
          }, 300);
        }
      };

      navigateAndHighlight();
    }
  }, [highlightPage, highlightQuote, highlightValue, activeTab]);

  // Determine available tabs
  const availableTabs: { id: ViewerTab; label: string }[] = [
    { id: "text", label: "Text" },
  ];

  if (hasPdf && sourceUrl) {
    availableTabs.push({ id: "pdf", label: "PDF" });
  }
  if (hasImage && sourceUrl) {
    availableTabs.push({ id: "image", label: "Image" });
  }
  if (extraction) {
    availableTabs.push({ id: "json", label: "JSON" });
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b bg-white">
        {availableTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
              activeTab === tab.id
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "text" && (
          <PageViewer
            pages={pages}
            highlightQuote={highlightQuote}
            highlightPage={highlightPage}
            highlightCharStart={highlightCharStart}
            highlightCharEnd={highlightCharEnd}
          />
        )}

        {activeTab === "pdf" && sourceUrl && (
          <PDFViewer
            ref={pdfViewerRef}
            url={sourceUrl}
            currentPage={highlightPage}
            highlightText={highlightValue || highlightQuote}
            highlightBboxes={highlightBboxes}
          />
        )}

        {activeTab === "image" && sourceUrl && (
          <div className="h-full overflow-auto p-4 bg-gray-100">
            <img
              src={sourceUrl}
              alt="Document"
              className="max-w-full h-auto mx-auto shadow-lg"
            />
          </div>
        )}

        {activeTab === "json" && extraction && (
          <div className="h-full overflow-auto p-4 bg-gray-900">
            <pre className="text-sm text-green-400 font-mono whitespace-pre-wrap">
              {JSON.stringify(extraction, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
