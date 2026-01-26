import { useState, useEffect, useCallback, useRef } from "react";

export interface AssessmentProgress {
  runId: string | null;
  status: "idle" | "connecting" | "running" | "completed" | "error";
  stage: string | null;
  stageStatus: string | null;
  inputTokens: number;
  outputTokens: number;
  decision: string | null;
  assessmentId: string | null;
  error: string | null;
}

interface UseAssessmentWebSocketReturn {
  progress: AssessmentProgress;
  startAssessment: (claimId: string) => Promise<string | null>;
  isRunning: boolean;
  reset: () => void;
}

const initialProgress: AssessmentProgress = {
  runId: null,
  status: "idle",
  stage: null,
  stageStatus: null,
  inputTokens: 0,
  outputTokens: 0,
  decision: null,
  assessmentId: null,
  error: null,
};

/**
 * Hook for managing assessment WebSocket connections and progress tracking.
 *
 * Usage:
 * ```tsx
 * const { progress, startAssessment, isRunning, reset } = useAssessmentWebSocket();
 *
 * const handleRunAssessment = async () => {
 *   const runId = await startAssessment(claimId);
 *   if (runId) {
 *     // Assessment started successfully
 *   }
 * };
 * ```
 */
export function useAssessmentWebSocket(): UseAssessmentWebSocketReturn {
  const [progress, setProgress] = useState<AssessmentProgress>(initialProgress);
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setProgress(initialProgress);
  }, [cleanup]);

  const connectWebSocket = useCallback((claimId: string, runId: string) => {
    cleanup();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/claims/${claimId}/assessment/ws/${runId}`;

    setProgress((prev) => ({
      ...prev,
      status: "connecting",
    }));

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setProgress((prev) => ({
        ...prev,
        status: "running",
      }));

      // Start ping interval
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("pong");
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "sync":
            setProgress((prev) => ({
              ...prev,
              status: msg.status === "running" ? "running" : prev.status,
              inputTokens: msg.input_tokens ?? prev.inputTokens,
              outputTokens: msg.output_tokens ?? prev.outputTokens,
            }));
            break;

          case "stage":
            setProgress((prev) => ({
              ...prev,
              stage: msg.stage,
              stageStatus: msg.status,
            }));
            break;

          case "tokens":
            setProgress((prev) => ({
              ...prev,
              inputTokens: msg.input,
              outputTokens: msg.output,
            }));
            break;

          case "complete":
            setProgress((prev) => ({
              ...prev,
              status: "completed",
              decision: msg.decision,
              assessmentId: msg.assessment_id,
              inputTokens: msg.input_tokens ?? prev.inputTokens,
              outputTokens: msg.output_tokens ?? prev.outputTokens,
            }));
            cleanup();
            break;

          case "error":
            setProgress((prev) => ({
              ...prev,
              status: "error",
              error: msg.message,
            }));
            cleanup();
            break;

          case "ping":
            ws.send("pong");
            break;
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = () => {
      setProgress((prev) => ({
        ...prev,
        status: "error",
        error: "WebSocket connection error",
      }));
      cleanup();
    };

    ws.onclose = () => {
      // Only set error if we weren't already in a terminal state
      setProgress((prev) => {
        if (prev.status === "running" || prev.status === "connecting") {
          return {
            ...prev,
            status: "error",
            error: "Connection closed unexpectedly",
          };
        }
        return prev;
      });
    };
  }, [cleanup]);

  const startAssessment = useCallback(async (claimId: string): Promise<string | null> => {
    try {
      // Reset state
      setProgress({
        ...initialProgress,
        status: "connecting",
      });

      // Start the assessment run
      const response = await fetch(`/api/claims/${claimId}/assessment/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ processing_type: "assessment" }),
      });

      if (!response.ok) {
        const error = await response.json();
        setProgress((prev) => ({
          ...prev,
          status: "error",
          error: error.detail || "Failed to start assessment",
        }));
        return null;
      }

      const data = await response.json();
      const runId = data.run_id;

      setProgress((prev) => ({
        ...prev,
        runId,
      }));

      // Connect WebSocket for progress updates
      connectWebSocket(claimId, runId);

      return runId;
    } catch (e) {
      setProgress((prev) => ({
        ...prev,
        status: "error",
        error: e instanceof Error ? e.message : "Failed to start assessment",
      }));
      return null;
    }
  }, [connectWebSocket]);

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  return {
    progress,
    startAssessment,
    isRunning: progress.status === "connecting" || progress.status === "running",
    reset,
  };
}
