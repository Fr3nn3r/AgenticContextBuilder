import { useState, useEffect } from "react";
import { ClaimsList } from "./components/ClaimsList";
import { DocReview } from "./components/DocReview";
import { RunSummary } from "./components/RunSummary";
import type { ClaimSummary, DocSummary } from "./types";
import { listClaims, listDocs } from "./api/client";

type View = "dashboard" | "review";

function App() {
  const [view, setView] = useState<View>("dashboard");
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [selectedClaim, setSelectedClaim] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load claims on mount
  useEffect(() => {
    loadClaims();
  }, []);

  async function loadClaims() {
    try {
      setLoading(true);
      setError(null);
      const data = await listClaims();
      setClaims(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectClaim(claimId: string) {
    try {
      setSelectedClaim(claimId);
      const data = await listDocs(claimId);
      setDocs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load docs");
    }
  }

  function handleSelectDoc(docId: string) {
    setSelectedDoc(docId);
    setView("review");
  }

  function handleBackToDashboard() {
    setView("dashboard");
    setSelectedDoc(null);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive mb-4">{error}</p>
          <button
            onClick={loadClaims}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold">Extraction QA Console</h1>
          {view === "review" && (
            <button
              onClick={handleBackToDashboard}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              &larr; Back to Dashboard
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-6">
        {view === "dashboard" ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Run summary */}
            <div className="lg:col-span-3">
              <RunSummary />
            </div>

            {/* Claims list */}
            <div className="lg:col-span-3">
              <ClaimsList
                claims={claims}
                selectedClaim={selectedClaim}
                docs={docs}
                onSelectClaim={handleSelectClaim}
                onSelectDoc={handleSelectDoc}
              />
            </div>
          </div>
        ) : (
          <DocReview
            docId={selectedDoc!}
            onBack={handleBackToDashboard}
            onSaved={loadClaims}
          />
        )}
      </main>
    </div>
  );
}

export default App;
