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
  });

  // Update callback refs when they change
  useEffect(() => {
    callbacksRef.current = {
      onDocProgress,
      onBatchComplete,
      onBatchCancelled,
      onSync,
      onError,
    };
  }, [onDocProgress, onBatchComplete, onBatchCancelled, onSync, onError]);

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
            if (callbacks.onBatchComplete && message.summary) {
              callbacks.onBatchComplete(message.summary);
            }
            break;

          case 'batch_cancelled':
          case 'run_cancelled':  // Support legacy message type
            if (callbacks.onBatchCancelled) {
              callbacks.onBatchCancelled();
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
      setIsReconnecting(false);
      wsRef.current = null;

      // Auto-reconnect if we should
      if (shouldReconnectRef.current && batchId) {
        setReconnectAttempts((prev) => prev + 1);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, WS_RECONNECT_DELAY);
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
