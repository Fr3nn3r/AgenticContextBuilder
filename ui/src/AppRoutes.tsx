import { Routes, Route, Navigate } from "react-router-dom";
import { BatchWorkspace } from "./components/BatchWorkspace";
import { ClaimsTable } from "./components/ClaimsTable";
import { ClaimReview } from "./components/ClaimReview";
import { ClassificationReview } from "./components/ClassificationReview";
import { DocumentReview } from "./components/DocumentReview";
import { ExtractionPage } from "./components/ExtractionPage";
import { TemplatesPage } from "./components/TemplatesPage";
import { MetricsPage } from "./components/metrics";
import { EvaluationPage } from "./components/evaluation";
import { NewClaimPage } from "./components/NewClaimPage";
import { PipelineControlCenter } from "./components/PipelineControlCenter";
import { TruthPage } from "./components/TruthPage";
import { DocumentDetailPage } from "./components/DocumentDetailPage";
import { DocumentsListPage } from "./components/DocumentsListPage";
import ProtectedRoute from "./components/ProtectedRoute";
import { AdminPage } from "./components/AdminPage";
import {
  ComplianceOverview,
  ComplianceLedger,
  ComplianceVerification,
  ComplianceVersionBundles,
  ComplianceControls,
} from "./pages/compliance";
import { useBatch } from "./context/BatchContext";
import { useClaims } from "./context/ClaimsContext";

export function AppRoutes() {
  // Claims - only need refreshClaims for ClaimReview callback
  const { refreshClaims } = useClaims();

  // Batch state - still needed for several components
  const {
    runs,
    selectedRunId,
    setSelectedRunId,
    detailedRuns,
    selectedDetailedRun,
    dashboardOverview,
    dashboardDocTypes,
    dashboardLoading,
    refreshRuns,
    isRefreshing,
  } = useBatch();

  return (
    <Routes>
      {/* Batch workspace routes */}
      <Route
        path="/batches"
        element={
          <BatchWorkspace
            batches={detailedRuns}
            selectedBatchId={selectedRunId}
            onBatchChange={setSelectedRunId}
            selectedBatch={selectedDetailedRun}
            onRefresh={refreshRuns}
            isRefreshing={isRefreshing}
          />
        }
      >
        <Route
          index
          element={
            selectedRunId ? (
              <Navigate to={selectedRunId} replace />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Loading batches...
              </div>
            )
          }
        />
        <Route
          path=":batchId"
          element={
            <ExtractionPage
              batches={detailedRuns}
              selectedBatchId={selectedRunId}
              onBatchChange={setSelectedRunId}
              selectedBatch={selectedDetailedRun}
              overview={dashboardOverview}
              docTypes={dashboardDocTypes}
              loading={dashboardLoading}
            />
          }
        />
        <Route
          path=":batchId/documents"
          element={
            <DocumentReview
              batches={runs}
              selectedBatchId={selectedRunId}
              onBatchChange={setSelectedRunId}
            />
          }
        />
        <Route
          path=":batchId/classification"
          element={
            <ClassificationReview
              batches={runs}
              selectedBatchId={selectedRunId}
              onBatchChange={setSelectedRunId}
            />
          }
        />
        <Route
          path=":batchId/claims"
          element={<ClaimsTable />}
        />
        <Route
          path=":batchId/metrics"
          element={
            <MetricsPage
              selectedBatchId={selectedRunId}
              onBatchChange={setSelectedRunId}
            />
          }
        />
        <Route
          path=":batchId/benchmark"
          element={<Navigate to="../metrics" replace />}
        />
      </Route>

      {/* Batch-independent routes */}
      <Route
        path="/claims/new"
        element={
          <ProtectedRoute screen="new-claim">
            <NewClaimPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/claims/all"
        element={<ClaimsTable showAllClaims />}
      />
      <Route
        path="/claims/:claimId/review"
        element={<ClaimReview onSaved={refreshClaims} selectedRunId={selectedRunId} />}
      />
      <Route
        path="/documents/:claimId/:docId"
        element={<DocumentDetailPage />}
      />
      <Route
        path="/templates"
        element={
          <ProtectedRoute screen="templates">
            <TemplatesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/pipeline"
        element={
          <ProtectedRoute screen="pipeline">
            <PipelineControlCenter />
          </ProtectedRoute>
        }
      />
      <Route
        path="/truth"
        element={
          <ProtectedRoute screen="ground-truth">
            <TruthPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute screen="admin">
            <AdminPage />
          </ProtectedRoute>
        }
      />

      {/* Compliance routes */}
      <Route
        path="/compliance"
        element={
          <ProtectedRoute screen="compliance">
            <ComplianceOverview />
          </ProtectedRoute>
        }
      />
      <Route
        path="/compliance/ledger"
        element={
          <ProtectedRoute screen="compliance">
            <ComplianceLedger />
          </ProtectedRoute>
        }
      />
      <Route
        path="/compliance/verification"
        element={
          <ProtectedRoute screen="compliance">
            <ComplianceVerification />
          </ProtectedRoute>
        }
      />
      <Route
        path="/compliance/version-bundles"
        element={
          <ProtectedRoute screen="compliance">
            <ComplianceVersionBundles />
          </ProtectedRoute>
        }
      />
      <Route
        path="/compliance/controls"
        element={
          <ProtectedRoute screen="compliance">
            <ComplianceControls />
          </ProtectedRoute>
        }
      />

      <Route path="/evaluation" element={<EvaluationPage />} />

      {/* All Documents page (batch-independent) */}
      <Route path="/documents" element={<DocumentsListPage />} />

      {/* Redirects for backwards compatibility */}
      <Route path="/" element={<Navigate to="/batches" replace />} />
      <Route path="/dashboard" element={<Navigate to="/batches" replace />} />
      <Route
        path="/classification"
        element={
          selectedRunId ? (
            <Navigate to={`/batches/${selectedRunId}/classification`} replace />
          ) : (
            <Navigate to="/batches" replace />
          )
        }
      />
      <Route
        path="/claims"
        element={
          selectedRunId ? (
            <Navigate to={`/batches/${selectedRunId}/claims`} replace />
          ) : (
            <Navigate to="/batches" replace />
          )
        }
      />
      <Route
        path="/insights"
        element={<Navigate to="/evaluation" replace />}
      />
    </Routes>
  );
}
