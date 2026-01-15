import { useEffect } from "react";
import { Outlet, useParams, useNavigate } from "react-router-dom";
import { BatchContextBar, BatchSubNav } from "./shared";
import type { DetailedRunInfo } from "../api/client";

interface BatchWorkspaceProps {
  batches: DetailedRunInfo[];
  selectedBatchId: string | null;
  onBatchChange: (batchId: string) => void;
  selectedBatch: DetailedRunInfo | null;
}

export function BatchWorkspace({
  batches,
  selectedBatchId,
  onBatchChange,
  selectedBatch,
}: BatchWorkspaceProps) {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();

  // Sync URL batchId to parent state
  useEffect(() => {
    if (batchId && batchId !== selectedBatchId) {
      // Check if batchId exists in batches
      const exists = batches.some((b) => b.run_id === batchId);
      if (exists) {
        onBatchChange(batchId);
      } else if (batches.length > 0) {
        // Invalid batchId, redirect to latest
        navigate(`/batches/${batches[0].run_id}`, { replace: true });
      }
    }
  }, [batchId, selectedBatchId, batches, onBatchChange, navigate]);

  // Handle batch change from dropdown - navigate to new batch
  const handleBatchChange = (newBatchId: string) => {
    onBatchChange(newBatchId);
    // Preserve current tab when changing batch
    const currentPath = window.location.pathname;
    const currentTab = currentPath.split("/").slice(3).join("/"); // e.g., "documents" or ""
    navigate(`/batches/${newBatchId}${currentTab ? `/${currentTab}` : ""}`);
  };

  // If no batchId in URL but we have a selected one, redirect
  useEffect(() => {
    if (!batchId && selectedBatchId) {
      navigate(`/batches/${selectedBatchId}`, { replace: true });
    } else if (!batchId && batches.length > 0) {
      navigate(`/batches/${batches[0].run_id}`, { replace: true });
    }
  }, [batchId, selectedBatchId, batches, navigate]);

  // Show empty state when no batches exist
  if (batches.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
            <svg
              className="w-8 h-8 text-muted-foreground"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">No batches found</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Run the pipeline to create your first batch. Batches contain extraction results from processing claims.
          </p>
          <div className="text-xs text-muted-foreground bg-muted rounded-md p-3 font-mono">
            python -m context_builder.cli extract -o output/claims
          </div>
        </div>
      </div>
    );
  }

  // Show loading state while redirecting
  if (!batchId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">Loading batches...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <BatchContextBar
        batches={batches}
        selectedBatchId={selectedBatchId}
        onBatchChange={handleBatchChange}
        selectedBatch={selectedBatch}
      />
      <BatchSubNav
        counts={
          selectedBatch
            ? {
                documents: selectedBatch.docs_total,
                claims: selectedBatch.claims_count,
              }
            : undefined
        }
      />
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
