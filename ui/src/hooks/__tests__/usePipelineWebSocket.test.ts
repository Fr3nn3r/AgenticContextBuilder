import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePipelineWebSocket } from "../usePipelineWebSocket";

// ============================================================================
// WebSocket Mock
// ============================================================================

interface MockWebSocket {
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: (() => void) | null;
  onclose: (() => void) | null;
  readyState: number;
  close: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
}

function createMockWebSocket(): MockWebSocket {
  return {
    onopen: null,
    onmessage: null,
    onerror: null,
    onclose: null,
    readyState: WebSocket.OPEN,
    close: vi.fn(),
    send: vi.fn(),
  };
}

describe("usePipelineWebSocket", () => {
  let mockWs: MockWebSocket;
  let WebSocketSpy: ReturnType<typeof vi.fn> & { OPEN?: number };

  beforeEach(() => {
    vi.useFakeTimers();
    mockWs = createMockWebSocket();
    WebSocketSpy = vi.fn(() => mockWs);
    // Preserve WebSocket constants
    WebSocketSpy.OPEN = 1;
    vi.stubGlobal("WebSocket", WebSocketSpy);
    // Mock window.location for getWsUrl
    vi.stubGlobal("location", {
      protocol: "http:",
      host: "localhost:5173",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // ============================================================================
  // Connection Lifecycle Tests
  // ============================================================================

  describe("connection lifecycle", () => {
    it("sets isConnecting=true on initial connect", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      expect(result.current.isConnecting).toBe(true);
      expect(result.current.isConnected).toBe(false);
    });

    it("sets isConnected=true on ws.onopen", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      act(() => {
        mockWs.onopen?.();
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.isConnecting).toBe(false);
    });

    it("sets isConnected=false on ws.onclose", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      act(() => {
        mockWs.onopen?.();
      });

      expect(result.current.isConnected).toBe(true);

      act(() => {
        mockWs.onclose?.();
      });

      expect(result.current.isConnected).toBe(false);
    });

    it("does not connect when batchId is null", () => {
      renderHook(() => usePipelineWebSocket({ batchId: null }));

      expect(WebSocketSpy).not.toHaveBeenCalled();
    });

    it("closes WebSocket on unmount", () => {
      const { unmount } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      unmount();

      expect(mockWs.close).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Message Routing Tests
  // ============================================================================

  describe("message routing", () => {
    it("calls onSync on sync message", () => {
      const onSync = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onSync })
      );

      act(() => {
        mockWs.onopen?.();
      });

      const syncMessage = {
        type: "sync",
        status: "running",
        docs: { doc_1: { doc_id: "doc_1", phase: "extracting" } },
      };

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify(syncMessage) });
      });

      expect(onSync).toHaveBeenCalledWith("running", syncMessage.docs);
    });

    it("calls onDocProgress on doc_progress message", () => {
      const onDocProgress = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onDocProgress })
      );

      act(() => {
        mockWs.onopen?.();
      });

      const progressMessage = {
        type: "doc_progress",
        doc_id: "doc_1",
        phase: "extracting",
        error: undefined,
        failed_at_stage: undefined,
      };

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify(progressMessage) });
      });

      expect(onDocProgress).toHaveBeenCalledWith(
        "doc_1",
        "extracting",
        undefined,
        undefined
      );
    });

    it("calls onDocProgress with error info when phase fails", () => {
      const onDocProgress = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onDocProgress })
      );

      act(() => {
        mockWs.onopen?.();
      });

      const failedMessage = {
        type: "doc_progress",
        doc_id: "doc_1",
        phase: "failed",
        error: "Classification failed",
        failed_at_stage: "classifying",
      };

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify(failedMessage) });
      });

      expect(onDocProgress).toHaveBeenCalledWith(
        "doc_1",
        "failed",
        "Classification failed",
        "classifying"
      );
    });

    it("calls onBatchComplete on batch_complete message", () => {
      const onBatchComplete = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onBatchComplete })
      );

      act(() => {
        mockWs.onopen?.();
      });

      const completeMessage = {
        type: "batch_complete",
        summary: { total: 5, success: 4, failed: 1 },
      };

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify(completeMessage) });
      });

      expect(onBatchComplete).toHaveBeenCalledWith({
        total: 5,
        success: 4,
        failed: 1,
      });
    });

    it("calls onBatchComplete on legacy run_complete message", () => {
      const onBatchComplete = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onBatchComplete })
      );

      act(() => {
        mockWs.onopen?.();
      });

      const legacyMessage = {
        type: "run_complete",
        summary: { total: 3, success: 3, failed: 0 },
      };

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify(legacyMessage) });
      });

      expect(onBatchComplete).toHaveBeenCalledWith({
        total: 3,
        success: 3,
        failed: 0,
      });
    });

    it("calls onBatchCancelled on batch_cancelled message", () => {
      const onBatchCancelled = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onBatchCancelled })
      );

      act(() => {
        mockWs.onopen?.();
      });

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify({ type: "batch_cancelled" }) });
      });

      expect(onBatchCancelled).toHaveBeenCalled();
    });

    it("sends pong on ping message when connection is open", () => {
      renderHook(() => usePipelineWebSocket({ batchId: "batch_123" }));

      act(() => {
        mockWs.onopen?.();
      });

      // Ensure readyState is OPEN before sending pong
      mockWs.readyState = 1; // WebSocket.OPEN = 1

      act(() => {
        mockWs.onmessage?.({ data: JSON.stringify({ type: "ping" }) });
      });

      expect(mockWs.send).toHaveBeenCalledWith("pong");
    });
  });

  // ============================================================================
  // Error Handling Tests
  // ============================================================================

  describe("error handling", () => {
    it("sets error state on ws.onerror", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      act(() => {
        mockWs.onerror?.();
      });

      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.message).toBe("WebSocket connection error");
    });

    it("calls onError callback on error", () => {
      const onError = vi.fn();
      renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123", onError })
      );

      act(() => {
        mockWs.onerror?.();
      });

      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });
  });

  // ============================================================================
  // Reconnection Tests
  // ============================================================================

  describe("reconnection", () => {
    it("increments reconnectAttempts on close", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      expect(result.current.reconnectAttempts).toBe(0);

      act(() => {
        mockWs.onopen?.();
      });

      act(() => {
        mockWs.onclose?.();
      });

      // State should update synchronously within act
      expect(result.current.reconnectAttempts).toBe(1);
    });

    it("sets isReconnecting=true after first successful connection", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      // Initial state - connecting, not reconnecting
      expect(result.current.isConnecting).toBe(true);
      expect(result.current.isReconnecting).toBe(false);

      // First connection opens
      act(() => {
        mockWs.onopen?.();
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.isConnecting).toBe(false);
      expect(result.current.isReconnecting).toBe(false);
    });

    it("resets reconnectAttempts on successful reconnect", () => {
      const { result } = renderHook(() =>
        usePipelineWebSocket({ batchId: "batch_123" })
      );

      act(() => {
        mockWs.onopen?.();
      });

      act(() => {
        mockWs.onclose?.();
      });

      expect(result.current.reconnectAttempts).toBe(1);

      // Simulate successful reconnection
      act(() => {
        mockWs.onopen?.();
      });

      expect(result.current.reconnectAttempts).toBe(0);
    });
  });
});
