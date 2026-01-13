/**
 * New Claim page for batch upload and pipeline execution.
 *
 * Features:
 * - Create multiple claims with documents
 * - Real-time pipeline progress via WebSocket
 * - Cancel with confirmation
 * - Results summary
 */

import { useCallback, useEffect, useState } from 'react';
import {
  cancelPipeline,
  deletePendingClaim,
  deletePendingDocument,
  listPendingClaims,
  startPipeline,
  uploadDocuments,
} from '../api/client';

// Generate claim ID locally with date + random suffix for uniqueness
function generateLocalClaimId(): string {
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
  const randomSuffix = Math.random().toString(36).substring(2, 6).toUpperCase();
  return `CLM-${dateStr}-${randomSuffix}`;
}
import { usePipelineWebSocket } from '../hooks/usePipelineWebSocket';
import type { DocProgress, PendingClaim, PipelineBatch, PipelineBatchStatus } from '../types';
import { PendingClaimCard } from './PendingClaimCard';
import { PipelineProgress } from './PipelineProgress';

type PageState = 'uploading' | 'running' | 'complete';

export function NewClaimPage() {
  const [pageState, setPageState] = useState<PageState>('uploading');
  const [pendingClaims, setPendingClaims] = useState<PendingClaim[]>([]);
  const [uploadingClaim, setUploadingClaim] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [loading, setLoading] = useState(true);

  // Pipeline state
  const [currentBatch, setCurrentBatch] = useState<PipelineBatch | null>(null);
  const [docs, setDocs] = useState<Record<string, DocProgress>>({});
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [isStarting, setIsStarting] = useState(false); // Shows while API call is in progress

  // WebSocket connection
  const { isConnected, isConnecting, isReconnecting } = usePipelineWebSocket({
    batchId: currentBatch?.batch_id || null,
    onDocProgress: (docId, phase, error, failedAtStage) => {
      setDocs((prev) => ({
        ...prev,
        [docId]: {
          ...prev[docId],
          phase: phase as DocProgress['phase'],
          error,
          failed_at_stage: failedAtStage as DocProgress['phase'] | undefined,
        },
      }));
    },
    onBatchComplete: (summary) => {
      setCurrentBatch((prev) =>
        prev ? { ...prev, status: 'completed', summary } : null
      );
      setPageState('complete');
    },
    onBatchCancelled: () => {
      setCurrentBatch((prev) =>
        prev ? { ...prev, status: 'cancelled' } : null
      );
      setPageState('complete');
    },
    onSync: (status, syncedDocs) => {
      setCurrentBatch((prev) =>
        prev ? { ...prev, status } : null
      );
      setDocs(syncedDocs);
    },
  });

  // Load pending claims on mount, auto-create one if none exist
  useEffect(() => {
    loadPendingClaims();
  }, []);

  const loadPendingClaims = async () => {
    try {
      const claims = await listPendingClaims();
      setPendingClaims(claims);

      // Auto-create a claim if none exist so user has a drop zone ready
      if (claims.length === 0) {
        const newClaimId = generateLocalClaimId();
        setPendingClaims([
          { claim_id: newClaimId, created_at: new Date().toISOString(), documents: [] },
        ]);
      }
    } catch (err) {
      console.error('Failed to load pending claims:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddClaim = () => {
    const newClaimId = generateLocalClaimId();
    setPendingClaims((prev) => [
      ...prev,
      { claim_id: newClaimId, created_at: new Date().toISOString(), documents: [] },
    ]);
  };

  const handleUpload = useCallback(async (claimId: string, files: File[]) => {
    setUploadingClaim(claimId);
    setUploadProgress(0);

    try {
      await uploadDocuments(claimId, files, (progress) => {
        setUploadProgress(progress);
      });
      await loadPendingClaims();
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploadingClaim(null);
      setUploadProgress(0);
    }
  }, []);

  const handleRemoveDocument = useCallback(async (claimId: string, docId: string) => {
    try {
      await deletePendingDocument(claimId, docId);
      await loadPendingClaims();
    } catch (err) {
      console.error('Failed to remove document:', err);
    }
  }, []);

  const handleRemoveClaim = useCallback(async (claimId: string) => {
    try {
      await deletePendingClaim(claimId);
      await loadPendingClaims();
    } catch (err) {
      console.error('Failed to remove claim:', err);
    }
  }, []);

  const handleRunPipeline = async () => {
    const claimsWithDocs = pendingClaims.filter((c) => c.documents.length > 0);
    if (claimsWithDocs.length === 0) return;

    setIsStarting(true);

    try {
      const result = await startPipeline(claimsWithDocs.map((c) => c.claim_id));

      // Initialize docs state from pending claims
      const initialDocs: Record<string, DocProgress> = {};
      claimsWithDocs.forEach((claim) => {
        claim.documents.forEach((doc) => {
          initialDocs[doc.doc_id] = {
            doc_id: doc.doc_id,
            claim_id: claim.claim_id,
            filename: doc.original_filename,
            phase: 'pending',
          };
        });
      });

      setCurrentBatch({
        batch_id: result.batch_id,
        status: result.status as PipelineBatchStatus,
        claim_ids: claimsWithDocs.map((c) => c.claim_id),
      });
      setDocs(initialDocs);
      setPageState('running');
    } catch (err) {
      console.error('Failed to start pipeline:', err);
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancel = async () => {
    if (!currentBatch) return;

    try {
      await cancelPipeline(currentBatch.batch_id);
      setShowCancelConfirm(false);
    } catch (err) {
      console.error('Failed to cancel pipeline:', err);
    }
  };

  const handleReset = () => {
    setCurrentBatch(null);
    setDocs({});
    setPendingClaims([]);
    setPageState('uploading');
  };

  const totalDocs = pendingClaims.reduce((sum, c) => sum + c.documents.length, 0);
  const canRun = totalDocs > 0 && !uploadingClaim;

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-muted">
      <div className="max-w-4xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">New Claim</h1>
          <p className="text-muted-foreground mt-1">
            {pageState === 'uploading' && 'Upload documents and run the extraction pipeline.'}
            {pageState === 'running' && 'Processing documents...'}
            {pageState === 'complete' && 'Pipeline completed.'}
          </p>
        </div>

        {/* Upload State */}
        {pageState === 'uploading' && (
          <div className="space-y-6">
            {/* Add Claim Button */}
            <div className="flex justify-start">
              <button
                onClick={handleAddClaim}
                className="flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
              >
                <PlusIcon className="w-5 h-5" />
                Add New Claim File
              </button>
            </div>

            {/* Pending Claims List */}
            {pendingClaims.length > 0 ? (
              <div className="space-y-4">
                {pendingClaims.map((claim) => (
                  <PendingClaimCard
                    key={claim.claim_id}
                    claimId={claim.claim_id}
                    documents={claim.documents}
                    onUpload={handleUpload}
                    onRemoveDocument={handleRemoveDocument}
                    onRemoveClaim={handleRemoveClaim}
                    uploading={uploadingClaim === claim.claim_id}
                    uploadProgress={uploadingClaim === claim.claim_id ? uploadProgress : 0}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-card rounded-lg border p-8 text-center text-muted-foreground">
                No claim files yet. Click "Add New Claim File" to create one.
              </div>
            )}

            {/* Run Button */}
            <div className="flex justify-end">
              <button
                onClick={handleRunPipeline}
                disabled={!canRun}
                className="px-6 py-3 bg-success text-white rounded-lg hover:bg-success/90 disabled:bg-muted disabled:cursor-not-allowed transition-colors font-medium"
              >
                Run Pipeline ({totalDocs} {totalDocs === 1 ? 'document' : 'documents'})
              </button>
            </div>
          </div>
        )}

        {/* Starting State - shown while API call is in progress */}
        {isStarting && (
          <div className="bg-card rounded-lg border p-8 text-center">
            <div className="flex flex-col items-center gap-3">
              <SpinnerIcon className="w-8 h-8 text-info animate-spin" />
              <p className="text-muted-foreground font-medium">Starting pipeline...</p>
              <p className="text-sm text-muted-foreground/70">Preparing documents for processing</p>
            </div>
          </div>
        )}

        {/* Running / Complete State */}
        {!isStarting && (pageState === 'running' || pageState === 'complete') && currentBatch && (
          <div className="space-y-6">
            <PipelineProgress
              batchId={currentBatch.batch_id}
              status={currentBatch.status}
              docs={docs}
              summary={currentBatch.summary}
              onCancel={() => setShowCancelConfirm(true)}
              isConnected={isConnected}
              isConnecting={isConnecting}
              isReconnecting={isReconnecting}
            />

            {pageState === 'complete' && (
              <div className="flex justify-end gap-3">
                <button
                  onClick={handleReset}
                  className="px-4 py-2 border border-border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  Upload More Claims
                </button>
                <a
                  href={`/claims?run_id=${currentBatch?.batch_id || ''}`}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
                >
                  View in Claims Review
                </a>
              </div>
            )}
          </div>
        )}

        {/* Cancel Confirmation Modal */}
        {showCancelConfirm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-card rounded-lg p-6 max-w-md mx-4">
              <h3 className="text-lg font-semibold mb-2">Cancel Pipeline?</h3>
              <p className="text-muted-foreground mb-4">
                Documents that have already been processed will be saved.
                Are you sure you want to cancel?
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  className="px-4 py-2 border border-border rounded-lg hover:bg-muted/50"
                >
                  Keep Running
                </button>
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 bg-destructive text-white rounded-lg hover:bg-destructive/90"
                >
                  Cancel Pipeline
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}
