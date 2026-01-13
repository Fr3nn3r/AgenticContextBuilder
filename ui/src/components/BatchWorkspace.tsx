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
      <BatchSubNav />
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
