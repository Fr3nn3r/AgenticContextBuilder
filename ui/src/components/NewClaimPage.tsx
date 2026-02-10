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
  runClaimAssessment,
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
import type { ClaimAssessmentProgress, DocProgress, PendingClaim, PipelineBatch, PipelineBatchStatus } from '../types';
import { AssessmentProgress } from './AssessmentProgress';
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

  // Force reprocess toggle
  const [forceReprocess, setForceReprocess] = useState(false);

  // Assessment state (auto-assess after extraction)
  const [assessmentProgress, setAssessmentProgress] = useState<Record<string, ClaimAssessmentProgress>>({});
  const [isAssessing, setIsAssessing] = useState(false);

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
      // Don't set pageState='complete' yet — assessment may follow
      // If no assessment_starting arrives within a moment, the WS will close
      // and we'll reach 'complete' via onAllAssessmentsComplete or the WS close
      if (!isAssessing) {
        setPageState('complete');
      }
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
      if (status === 'assessing') {
        setIsAssessing(true);
      }
    },
    // Assessment callbacks
    onAssessmentStarting: (claimIds) => {
      setIsAssessing(true);
      setPageState('running');
      setCurrentBatch((prev) =>
        prev ? { ...prev, status: 'assessing' as PipelineBatchStatus } : null
      );
      const initial: Record<string, ClaimAssessmentProgress> = {};
      claimIds.forEach((cid) => {
        initial[cid] = { claim_id: cid, phase: 'pending' };
      });
      setAssessmentProgress(initial);
    },
    onAssessmentStage: (claimId, stage, status) => {
      setAssessmentProgress((prev) => {
        const current = prev[claimId];
        // Don't overwrite terminal states (error/complete) with a stage update
        if (current?.phase === 'error' || current?.phase === 'complete') {
          return prev;
        }
        // If the stage itself reports an error, mark as error with failedAtStage
        if (status === 'error') {
          return {
            ...prev,
            [claimId]: {
              ...current,
              claim_id: claimId,
              phase: 'error',
              failed_at_stage: stage as ClaimAssessmentProgress['phase'],
            },
          };
        }
        return {
          ...prev,
          [claimId]: {
            ...current,
            claim_id: claimId,
            phase: stage as ClaimAssessmentProgress['phase'],
          },
        };
      });
    },
    onAssessmentComplete: (claimId, decision, assessmentId) => {
      setAssessmentProgress((prev) => ({
        ...prev,
        [claimId]: {
          ...prev[claimId],
          claim_id: claimId,
          phase: 'complete',
          decision,
          assessment_id: assessmentId,
        },
      }));
    },
    onAssessmentError: (claimId, error) => {
      setAssessmentProgress((prev) => ({
        ...prev,
        [claimId]: {
          ...prev[claimId],
          claim_id: claimId,
          phase: 'error',
          error,
          // Preserve failed_at_stage if already set by onAssessmentStage
          failed_at_stage: prev[claimId]?.failed_at_stage ?? prev[claimId]?.phase as ClaimAssessmentProgress['phase'],
        },
      }));
    },
    onAllAssessmentsComplete: () => {
      setIsAssessing(false);
      setPageState('complete');
      setCurrentBatch((prev) =>
        prev ? { ...prev, status: 'completed' } : null
      );
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
    // Always remove from local state (claim may only exist locally if no docs uploaded yet)
    setPendingClaims((prev) => prev.filter((c) => c.claim_id !== claimId));
    try {
      await deletePendingClaim(claimId);
    } catch {
      // 404 expected for locally-created claims with no uploads
    }
  }, []);

  const handleRunPipeline = async () => {
    const claimsWithDocs = pendingClaims.filter((c) => c.documents.length > 0);
    if (claimsWithDocs.length === 0) return;

    setIsStarting(true);

    try {
      const result = await startPipeline(claimsWithDocs.map((c) => c.claim_id), 'gpt-4o', true, forceReprocess);

      // Initialize docs state from pending claims
      const initialDocs: Record<string, DocProgress> = {};
      claimsWithDocs.forEach((claim) => {
        claim.documents.forEach((doc) => {
          initialDocs[doc.doc_id] = {
            doc_id: doc.doc_id,
            claim_id: claim.claim_id,
            filename: doc.original_filename,
            phase: 'pending',
            file_md5: doc.file_md5,
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
    setAssessmentProgress({});
    setIsAssessing(false);
    setPendingClaims([]);
    setPageState('uploading');
  };

  // Retry failed assessments
  const [isRetryingAssessment, setIsRetryingAssessment] = useState(false);

  const handleRetryAssessment = async (claimIds: string[]) => {
    if (claimIds.length === 0) return;
    setIsRetryingAssessment(true);

    // Reset failed claims to pending state
    setAssessmentProgress((prev) => {
      const updated = { ...prev };
      claimIds.forEach((cid) => {
        updated[cid] = { claim_id: cid, phase: 'pending' };
      });
      return updated;
    });
    setIsAssessing(true);
    setPageState('running');

    // Run each claim assessment sequentially via per-claim endpoint
    for (const cid of claimIds) {
      setAssessmentProgress((prev) => ({
        ...prev,
        [cid]: { ...prev[cid], claim_id: cid, phase: 'reconciliation' },
      }));
      try {
        // Start assessment (returns immediately with run_id)
        const startResult = await runClaimAssessment(cid);
        const runId = (startResult as unknown as { run_id: string }).run_id;
        if (!runId) throw new Error('No run_id returned from assessment start');

        // Poll status until assessment completes
        const result = await pollAssessmentStatus(cid, runId);
        const completed = result.status === 'completed' && result.result;
        if (completed) {
          const { decision, id } = result.result!;
          setAssessmentProgress((prev) => ({
            ...prev,
            [cid]: {
              claim_id: cid,
              phase: 'complete',
              decision,
              assessment_id: id,
            },
          }));
        } else if (result.status === 'error') {
          throw new Error(result.error || 'Assessment failed');
        }
      } catch (err) {
        console.error(`Assessment retry failed for ${cid}:`, err);
        setAssessmentProgress((prev) => ({
          ...prev,
          [cid]: {
            claim_id: cid,
            phase: 'error',
            error: err instanceof Error ? err.message : 'Retry failed. Please try again.',
            failed_at_stage: prev[cid]?.phase as ClaimAssessmentProgress['phase'],
          },
        }));
      }
    }

    setIsAssessing(false);
    setPageState('complete');
    setIsRetryingAssessment(false);
  };

  /** Poll assessment status endpoint until terminal state. */
  async function pollAssessmentStatus(
    claimId: string,
    runId: string,
    intervalMs = 2000,
    maxAttempts = 150, // 5 minutes
  ): Promise<{ status: string; result?: { decision: string; id: string }; error?: string }> {
    for (let i = 0; i < maxAttempts; i++) {
      const res = await fetch(`/api/claims/${encodeURIComponent(claimId)}/assessment/status/${encodeURIComponent(runId)}`);
      if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
      const data = await res.json();
      if (data.status !== 'running') return data;
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    throw new Error('Assessment timed out');
  }

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
      <div className="max-w-6xl mx-auto py-6 px-4 sm:px-6">
        {/* Header */}
        <div className="mb-4 flex items-baseline justify-between">
          <div className="flex items-baseline gap-3">
            <h1 className="text-xl font-semibold text-foreground tracking-tight">New Claim</h1>
            <span className="text-sm text-muted-foreground">
              {pageState === 'uploading' && 'Upload documents and run the extraction pipeline.'}
              {pageState === 'running' && !isAssessing && 'Processing documents...'}
              {pageState === 'running' && isAssessing && 'Assessing claims...'}
              {pageState === 'complete' && 'Pipeline completed.'}
            </span>
          </div>
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
            <div className="flex items-center justify-end gap-4">
              <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={forceReprocess}
                  onChange={(e) => setForceReprocess(e.target.checked)}
                  className="rounded border-border"
                />
                Force reprocess
              </label>
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
              status={isAssessing ? 'completed' as PipelineBatchStatus : currentBatch.status}
              docs={docs}
              claimIds={currentBatch.claim_ids}
              summary={currentBatch.summary}
              onCancel={!isAssessing ? () => setShowCancelConfirm(true) : undefined}
              isConnected={isConnected}
              isConnecting={isConnecting}
              isReconnecting={isReconnecting}
            />

            {/* Assessment Progress (shown during/after assessment) */}
            {Object.keys(assessmentProgress).length > 0 && (
              <AssessmentProgress
                claims={assessmentProgress}
                phase={isAssessing ? 'running' : pageState === 'complete' ? 'complete' : 'idle'}
                onRetry={handleRetryAssessment}
                isRetrying={isRetryingAssessment}
              />
            )}

            {pageState === 'complete' && (
              <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                <button
                  onClick={handleReset}
                  className="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-muted/50 transition-colors"
                >
                  Upload More Claims
                </button>
                <a
                  href={`/batches/${currentBatch?.batch_id}/documents`}
                  className="px-3 py-1.5 text-sm bg-accent text-white rounded-lg hover:bg-accent/90 transition-colors"
                >
                  View in Batches
                </a>
                {/* Per-claim assessment links */}
                {Object.values(assessmentProgress)
                  .filter((c) => c.phase === 'complete')
                  .map((c) => (
                    <a
                      key={c.claim_id}
                      href={`/claims/${c.claim_id}`}
                      className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                    >
                      View {c.claim_id} Assessment
                    </a>
                  ))}
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
