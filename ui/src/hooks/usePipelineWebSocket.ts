/**
 * WebSocket hook for real-time pipeline progress updates.
 *
 * Features:
 * - Auto-reconnect on disconnect (3s delay)
 * - State sync on reconnect
 * - Ping/pong keepalive
 * - Callbacks for progress, completion, and errors
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { DocProgress, PipelineBatchStatus, WebSocketMessage } from '../types';

const WS_RECONNECT_DELAY = 3000;
const WS_MAX_RECONNECT_ATTEMPTS = 10;

// Build WebSocket URL from current location
function getWsUrl(batchId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/api/pipeline/ws/${batchId}`;
}

export interface UsePipelineWebSocketOptions {
  batchId: string | null;
  onDocProgress?: (docId: string, phase: string, error?: string, failedAtStage?: string) => void;
  onBatchComplete?: (summary: { total: number; success: number; failed: number }) => void;
  onBatchCancelled?: () => void;
  onSync?: (status: PipelineBatchStatus, docs: Record<string, DocProgress>) => void;
  onError?: (error: Error) => void;
  // Assessment callbacks (auto-assess)
  onAssessmentStarting?: (claimIds: string[]) => void;
  onAssessmentStage?: (claimId: string, stage: string, status: string) => void;
  onAssessmentComplete?: (claimId: string, decision: string, assessmentId: string) => void;
  onAssessmentError?: (claimId: string, error: string) => void;
  onAllAssessmentsComplete?: (results: Array<{ claim_id: string; decision: string; assessment_id: string }>) => void;
}

export interface UsePipelineWebSocketResult {
  isConnected: boolean;
  isConnecting: boolean;
  isReconnecting: boolean;
  error: Error | null;
  reconnectAttempts: number;
}

export function usePipelineWebSocket({
  batchId,
  onDocProgress,
  onBatchComplete,
  onBatchCancelled,
  onSync,
  onError,
  onAssessmentStarting,
  onAssessmentStage,
  onAssessmentComplete,
  onAssessmentError,
  onAllAssessmentsComplete,
}: UsePipelineWebSocketOptions): UsePipelineWebSocketResult {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const hasConnectedOnceRef = useRef(false);

  // Store callbacks in refs to avoid reconnecting when they change
  const callbacksRef = useRef({
    onDocProgress,
    onBatchComplete,
    onBatchCancelled,
    onSync,
    onError,
    onAssessmentStarting,
    onAssessmentStage,
    onAssessmentComplete,
    onAssessmentError,
    onAllAssessmentsComplete,
  });

  // Update callback refs when they change
  useEffect(() => {
    callbacksRef.current = {
      onDocProgress,
      onBatchComplete,
      onBatchCancelled,
      onSync,
      onError,
      onAssessmentStarting,
      onAssessmentStage,
      onAssessmentComplete,
      onAssessmentError,
      onAllAssessmentsComplete,
    };
  }, [onDocProgress, onBatchComplete, onBatchCancelled, onSync, onError, onAssessmentStarting, onAssessmentStage, onAssessmentComplete, onAssessmentError, onAllAssessmentsComplete]);

  const connect = useCallback(() => {
    if (!batchId) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Distinguish initial connect from reconnect
    if (hasConnectedOnceRef.current) {
      setIsReconnecting(true);
      setIsConnecting(false);
    } else {
      setIsConnecting(true);
      setIsReconnecting(false);
    }
    setError(null);

    const ws = new WebSocket(getWsUrl(batchId));
    wsRef.current = ws;

    ws.onopen = () => {
      hasConnectedOnceRef.current = true;
      setIsConnected(true);
      setIsConnecting(false);
      setIsReconnecting(false);
      setReconnectAttempts(0);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        const callbacks = callbacksRef.current;

        switch (message.type) {
          case 'sync':
            if (callbacks.onSync && message.status && message.docs) {
              callbacks.onSync(message.status as PipelineBatchStatus, message.docs);
            }
            break;

          case 'doc_progress':
            if (callbacks.onDocProgress && message.doc_id && message.phase) {
              callbacks.onDocProgress(message.doc_id, message.phase, message.error, message.failed_at_stage);
            }
            break;

          case 'batch_complete':
          case 'run_complete':  // Support legacy message type
            shouldReconnectRef.current = false;
            if (callbacks.onBatchComplete && message.summary) {
              callbacks.onBatchComplete(message.summary);
            }
            break;

          case 'batch_cancelled':
          case 'run_cancelled':  // Support legacy message type
            shouldReconnectRef.current = false;
            if (callbacks.onBatchCancelled) {
              callbacks.onBatchCancelled();
            }
            break;

          case 'assessment_starting':
            if (callbacks.onAssessmentStarting && message.claim_ids) {
              callbacks.onAssessmentStarting(message.claim_ids);
            }
            break;

          case 'assessment_stage':
            if (callbacks.onAssessmentStage && message.claim_id && message.stage) {
              callbacks.onAssessmentStage(message.claim_id, message.stage, message.status || 'running');
            }
            break;

          case 'assessment_complete':
            if (callbacks.onAssessmentComplete && message.claim_id && message.decision) {
              callbacks.onAssessmentComplete(message.claim_id, message.decision, message.assessment_id || '');
            }
            break;

          case 'assessment_error':
            if (callbacks.onAssessmentError && message.claim_id && message.error) {
              callbacks.onAssessmentError(message.claim_id, message.error);
            }
            break;

          case 'all_assessments_complete':
            if (callbacks.onAllAssessmentsComplete && message.results) {
              callbacks.onAllAssessmentsComplete(message.results);
            }
            break;

          case 'error':
            // Server says run not found or other terminal error — stop reconnecting
            shouldReconnectRef.current = false;
            {
              const wsError = new Error(message.message || 'Server error');
              setError(wsError);
              if (callbacks.onError) {
                callbacks.onError(wsError);
              }
            }
            break;

          case 'ping':
            // Respond with pong to keep connection alive
            if (ws.readyState === WebSocket.OPEN) {
              ws.send('pong');
            }
            break;
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    ws.onerror = () => {
      const wsError = new Error('WebSocket connection error');
      setError(wsError);
      if (callbacksRef.current.onError) {
        callbacksRef.current.onError(wsError);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsConnecting(false);
      wsRef.current = null;

      // Auto-reconnect if we should (with max attempts safety net)
      if (shouldReconnectRef.current && batchId) {
        // Show reconnecting state immediately (not after the delay)
        setIsReconnecting(true);
        setReconnectAttempts((prev) => {
          if (prev >= WS_MAX_RECONNECT_ATTEMPTS) {
            setIsReconnecting(false);
            const maxError = new Error(`WebSocket reconnect failed after ${WS_MAX_RECONNECT_ATTEMPTS} attempts`);
            setError(maxError);
            if (callbacksRef.current.onError) {
              callbacksRef.current.onError(maxError);
            }
            return prev;
          }
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, WS_RECONNECT_DELAY);
          return prev + 1;
        });
      } else {
        setIsReconnecting(false);
      }
    };
  }, [batchId]);

  // Connect when batchId changes
  useEffect(() => {
    shouldReconnectRef.current = true;
    hasConnectedOnceRef.current = false; // Reset for new run

    if (batchId) {
      connect();
    }

    return () => {
      shouldReconnectRef.current = false;

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [batchId, connect]);

  return {
    isConnected,
    isConnecting,
    isReconnecting,
    error,
    reconnectAttempts,
  };
}
