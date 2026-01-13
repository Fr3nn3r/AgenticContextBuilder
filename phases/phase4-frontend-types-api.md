# Phase 4: Frontend Types & API - Complete

## Summary
Added TypeScript types and API client functions for upload and pipeline operations, plus a WebSocket hook for real-time progress.

## Files Created
- `ui/src/hooks/usePipelineWebSocket.ts` - WebSocket hook with:
  - Auto-reconnect on disconnect (3s delay)
  - State sync on reconnect
  - Ping/pong keepalive
  - Callbacks: onDocProgress, onRunComplete, onRunCancelled, onSync, onError

## Files Modified

### `ui/src/types/index.ts`
Added types:
- `PendingDocument` - Uploaded document in staging
- `PendingClaim` - Claim with pending documents
- `DocPipelinePhase` - "pending" | "ingesting" | "classifying" | "extracting" | "done" | "failed"
- `DocProgress` - Per-document progress tracking
- `PipelineRunStatus` - "pending" | "running" | "completed" | "failed" | "cancelled"
- `PipelineRun` - Pipeline run with status, docs, summary
- `WebSocketMessageType` - Message type enum
- `WebSocketMessage` - WebSocket protocol message

### `ui/src/api/client.ts`
Added functions:

**Upload Operations:**
- `uploadDocuments(claimId, files, onProgress?)` - Upload with progress callback
- `listPendingClaims()` - List all pending claims
- `getPendingClaim(claimId)` - Get single pending claim
- `deletePendingClaim(claimId)` - Remove claim from staging
- `deletePendingDocument(claimId, docId)` - Remove single document
- `reorderDocuments(claimId, docIds)` - Reorder documents in claim
- `validateClaimId(claimId)` - Check if claim ID is available

**Pipeline Operations:**
- `startPipeline(claimIds, model?)` - Start pipeline execution
- `cancelPipeline(runId)` - Cancel running pipeline
- `getPipelineStatus(runId)` - Get run status
- `listPipelineRuns()` - List all runs

## WebSocket Hook Usage
```typescript
const { isConnected, isConnecting, error, reconnectAttempts } = usePipelineWebSocket({
  runId: 'run_123',
  onDocProgress: (docId, phase, error) => { /* update UI */ },
  onRunComplete: (summary) => { /* show results */ },
  onRunCancelled: () => { /* handle cancel */ },
  onSync: (status, docs) => { /* sync state on reconnect */ },
});
```

## Key Features
- Upload progress tracking via XMLHttpRequest (fetch doesn't support upload progress)
- Auto-reconnect WebSocket with exponential backoff
- Type-safe API responses matching backend types
