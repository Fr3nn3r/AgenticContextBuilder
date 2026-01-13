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
import type { DocProgress, PipelineRunStatus, WebSocketMessage } from '../types';

const WS_RECONNECT_DELAY = 3000;

// Build WebSocket URL from current location
function getWsUrl(runId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/api/pipeline/ws/${runId}`;
}

export interface UsePipelineWebSocketOptions {
  runId: string | null;
  onDocProgress?: (docId: string, phase: string, error?: string, failedAtStage?: string) => void;
  onRunComplete?: (summary: { total: number; success: number; failed: number }) => void;
  onRunCancelled?: () => void;
  onSync?: (status: PipelineRunStatus, docs: Record<string, DocProgress>) => void;
  onError?: (error: Error) => void;
}

export interface UsePipelineWebSocketResult {
  isConnected: boolean;
  isConnecting: boolean;
  error: Error | null;
  reconnectAttempts: number;
}

export function usePipelineWebSocket({
  runId,
  onDocProgress,
  onRunComplete,
  onRunCancelled,
  onSync,
  onError,
}: UsePipelineWebSocketOptions): UsePipelineWebSocketResult {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);

  // Store callbacks in refs to avoid reconnecting when they change
  const callbacksRef = useRef({
    onDocProgress,
    onRunComplete,
    onRunCancelled,
    onSync,
    onError,
  });

  // Update callback refs when they change
  useEffect(() => {
    callbacksRef.current = {
      onDocProgress,
      onRunComplete,
      onRunCancelled,
      onSync,
      onError,
    };
  }, [onDocProgress, onRunComplete, onRunCancelled, onSync, onError]);

  const connect = useCallback(() => {
    if (!runId) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnecting(true);
    setError(null);

    const ws = new WebSocket(getWsUrl(runId));
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setIsConnecting(false);
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
              callbacks.onSync(message.status as PipelineRunStatus, message.docs);
            }
            break;

          case 'doc_progress':
            if (callbacks.onDocProgress && message.doc_id && message.phase) {
              callbacks.onDocProgress(message.doc_id, message.phase, message.error, message.failed_at_stage);
            }
            break;

          case 'run_complete':
            if (callbacks.onRunComplete && message.summary) {
              callbacks.onRunComplete(message.summary);
            }
            break;

          case 'run_cancelled':
            if (callbacks.onRunCancelled) {
              callbacks.onRunCancelled();
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

      // Auto-reconnect if we should
      if (shouldReconnectRef.current && runId) {
        setReconnectAttempts((prev) => prev + 1);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, WS_RECONNECT_DELAY);
      }
    };
  }, [runId]);

  // Connect when runId changes
  useEffect(() => {
    shouldReconnectRef.current = true;

    if (runId) {
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
  }, [runId, connect]);

  return {
    isConnected,
    isConnecting,
    error,
    reconnectAttempts,
  };
}
