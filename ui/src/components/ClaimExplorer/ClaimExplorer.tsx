import { useState, useEffect, useCallback } from "react";
import { X, Folder, FileText, RefreshCw } from "lucide-react";
import { ClaimTree } from "./ClaimTree";
import { ClaimSummaryTab } from "./ClaimSummaryTab";
import { DocumentTab } from "./DocumentTab";
import { listClaims, listDocs } from "../../api/client";
import type { ClaimSummary, DocSummary } from "../../types";
import { cn } from "../../lib/utils";
import { ThemePopover, HeaderUserMenu } from "../shared";

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
  docsLoading?: boolean;
}

interface Tab {
  id: string;
  type: "claim" | "document";
  claimId: string;
  docId?: string;
  label: string;
  // Initial highlight info for document tabs opened via "View source"
  initialHighlightPage?: number;
  initialHighlightCharStart?: number;
  initialHighlightCharEnd?: number;
}

export function ClaimExplorer() {
  const [claims, setClaims] = useState<ClaimWithDocs[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);

  // Load claims on mount
  useEffect(() => {
    loadClaims();
  }, []);

  const loadClaims = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listClaims();
      setClaims(data.map((c) => ({ ...c, documents: undefined, docsLoading: false })));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  };

  // Load documents for a claim
  const loadDocsForClaim = useCallback(async (claimId: string) => {
    setClaims((prev) =>
      prev.map((c) =>
        c.claim_id === claimId ? { ...c, docsLoading: true } : c
      )
    );

    try {
      const docs = await listDocs(claimId);
      setClaims((prev) =>
        prev.map((c) =>
          c.claim_id === claimId
            ? { ...c, documents: docs, docsLoading: false }
            : c
        )
      );
    } catch (err) {
      console.error("Failed to load docs for claim:", err);
      setClaims((prev) =>
        prev.map((c) =>
          c.claim_id === claimId ? { ...c, docsLoading: false } : c
        )
      );
    }
  }, []);

  // Find claim helper
  const findClaim = (claimId: string): ClaimWithDocs | undefined =>
    claims.find((c) => c.claim_id === claimId);

  // Find document helper
  const findDocument = (
    claimId: string,
    docId: string
  ): DocSummary | undefined =>
    findClaim(claimId)?.documents?.find((d) => d.doc_id === docId);

  // Handle claim selection from tree
  const handleSelectClaim = useCallback(
    (claimId: string) => {
      setSelectedClaimId(claimId);

      // Load docs if not already loaded
      const claim = claims.find((c) => c.claim_id === claimId);
      if (claim && !claim.documents && !claim.docsLoading) {
        loadDocsForClaim(claimId);
      }

      const tabId = `claim-${claimId}`;
      const existingTab = tabs.find((t) => t.id === tabId);

      if (existingTab) {
        setActiveTabId(tabId);
      } else {
        const newTab: Tab = {
          id: tabId,
          type: "claim",
          claimId,
          label: claimId,
        };
        setTabs((prev) => [...prev, newTab]);
        setActiveTabId(tabId);
      }
    },
    [claims, tabs, loadDocsForClaim]
  );

  // Handle document click from within ClaimSummaryTab (e.g., DocumentsPanel)
  const handleDocumentClick = useCallback(
    (claimId: string, docId: string) => {
      const tabId = `doc-${docId}`;
      const existingTab = tabs.find((t) => t.id === tabId);

      if (existingTab) {
        setActiveTabId(tabId);
      } else {
        const doc = findDocument(claimId, docId);
        const newTab: Tab = {
          id: tabId,
          type: "document",
          claimId,
          docId,
          label: doc?.filename || docId,
        };
        setTabs((prev) => [...prev, newTab]);
        setActiveTabId(tabId);
      }
    },
    [tabs, claims]
  );

  // Handle "View source" from facts - opens document with highlight
  const handleViewSource = useCallback(
    (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => {
      // Find which claim this doc belongs to
      const claimWithDoc = claims.find((c) =>
        c.documents?.some((d) => d.doc_id === docId)
      );
      if (!claimWithDoc) {
        console.warn("Could not find claim for doc:", docId);
        return;
      }

      const tabId = `doc-${docId}`;
      const existingTabIndex = tabs.findIndex((t) => t.id === tabId);

      const doc = findDocument(claimWithDoc.claim_id, docId);
      const newTab: Tab = {
        id: tabId,
        type: "document",
        claimId: claimWithDoc.claim_id,
        docId,
        label: doc?.filename || docId,
        initialHighlightPage: page ?? undefined,
        initialHighlightCharStart: charStart ?? undefined,
        initialHighlightCharEnd: charEnd ?? undefined,
      };

      if (existingTabIndex >= 0) {
        // Replace existing tab with new highlight info
        setTabs((prev) => {
          const updated = [...prev];
          updated[existingTabIndex] = newTab;
          return updated;
        });
      } else {
        setTabs((prev) => [...prev, newTab]);
      }
      setActiveTabId(tabId);
    },
    [tabs, claims]
  );

  // Close tab
  const handleCloseTab = (tabId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const tabIndex = tabs.findIndex((t) => t.id === tabId);
    const newTabs = tabs.filter((t) => t.id !== tabId);
    setTabs(newTabs);

    if (activeTabId === tabId) {
      if (newTabs.length === 0) {
        setActiveTabId(null);
        setSelectedClaimId(null);
      } else {
        const newIndex = Math.min(tabIndex, newTabs.length - 1);
        const newActiveTab = newTabs[newIndex];
        setActiveTabId(newActiveTab.id);
        setSelectedClaimId(newActiveTab.claimId);
      }
    }
  };

  // Get active tab content
  const activeTab = tabs.find((t) => t.id === activeTabId);
  const activeClaim = activeTab ? findClaim(activeTab.claimId) : null;
  const activeDocument =
    activeTab?.type === "document" && activeTab.docId
      ? findDocument(activeTab.claimId, activeTab.docId)
      : null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-background">
        <h1 className="text-xl font-semibold text-foreground">
          Claim Explorer
        </h1>
        <div className="flex items-center gap-3">
          <button
            onClick={loadClaims}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            Refresh
          </button>
          <div className="border-l border-border pl-3 flex items-center gap-2">
            <ThemePopover />
            <HeaderUserMenu />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0">
        {/* Left Claims List */}
        <div className="w-64 border-r border-border bg-background flex-shrink-0">
          <ClaimTree
            claims={claims}
            loading={loading}
            error={error}
            selectedClaimId={selectedClaimId}
            selectedDocId={activeTab?.type === "document" ? activeTab.docId : null}
            onSelectClaim={handleSelectClaim}
            onSelectDocument={handleDocumentClick}
          />
        </div>

        {/* Right Content Panel */}
        <div className="flex-1 flex flex-col min-w-0 bg-muted/20">
          {/* Tabs Bar */}
          {tabs.length > 0 && (
            <div className="flex border-b border-border bg-background overflow-x-auto">
              {tabs.map((tab) => (
                <div
                  key={tab.id}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 border-r border-border cursor-pointer transition-colors min-w-0 max-w-[200px] group",
                    activeTabId === tab.id
                      ? "bg-background border-b-2 border-b-primary -mb-px"
                      : "bg-muted/50 hover:bg-muted"
                  )}
                  onClick={() => {
                    setActiveTabId(tab.id);
                    setSelectedClaimId(tab.claimId);
                  }}
                >
                  {tab.type === "claim" ? (
                    <Folder className="h-4 w-4 text-amber-500 flex-shrink-0" />
                  ) : (
                    <FileText className="h-4 w-4 text-red-500 flex-shrink-0" />
                  )}
                  <span className="text-sm truncate flex-1">{tab.label}</span>
                  <button
                    className="p-0.5 rounded hover:bg-muted-foreground/20 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                    onClick={(e) => handleCloseTab(tab.id, e)}
                  >
                    <X className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Tab Content */}
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeTab && activeClaim ? (
              activeTab.type === "claim" ? (
                <ClaimSummaryTab
                  claim={activeClaim}
                  onDocumentClick={(docId) =>
                    handleDocumentClick(activeClaim.claim_id, docId)
                  }
                  onViewSource={handleViewSource}
                />
              ) : activeDocument ? (
                <DocumentTab
                  key={`${activeTab.id}-${activeTab.initialHighlightPage}-${activeTab.initialHighlightCharStart}`}
                  docSummary={activeDocument}
                  claimId={activeTab.claimId}
                  initialHighlightPage={activeTab.initialHighlightPage}
                  initialHighlightCharStart={activeTab.initialHighlightCharStart}
                  initialHighlightCharEnd={activeTab.initialHighlightCharEnd}
                />
              ) : null
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-8">
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                  <Folder className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="text-lg font-medium text-foreground mb-2">
                  Select a Claim
                </h3>
                <p className="text-sm text-muted-foreground max-w-md">
                  Choose a claim from the list on the left to view its summary,
                  extracted facts, and assessment details.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
