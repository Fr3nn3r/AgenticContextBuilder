import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getTruthEntries, listClaimRuns } from "../api/client";
import type { TruthEntry, TruthListResponse } from "../types";

const EMPTY_RESPONSE: TruthListResponse = { runs: [], entries: [] };

type OutcomeFilter = "" | "correct" | "incorrect" | "missing" | "unverifiable" | "unlabeled";

export function TruthPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<TruthListResponse>(EMPTY_RESPONSE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [availableRuns, setAvailableRuns] = useState<string[]>([]);

  // Filters
  const [search, setSearch] = useState("");
  const [docType, setDocType] = useState("");
  const [claimId, setClaimId] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [runId, setRunId] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [state, setState] = useState("");
  const [outcome, setOutcome] = useState<OutcomeFilter>("");
  const [fileMd5, setFileMd5] = useState("");
  const [reviewedAfter, setReviewedAfter] = useState("");
  const [reviewedBefore, setReviewedBefore] = useState("");

  useEffect(() => {
    listClaimRuns()
      .then((runs) => setAvailableRuns(runs.map((r) => r.run_id)))
      .catch(() => setAvailableRuns([]));
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    getTruthEntries({
      search: search || undefined,
      file_md5: fileMd5 || undefined,
      doc_type: docType || undefined,
      claim_id: claimId || undefined,
      reviewer: reviewer || undefined,
      run_id: runId || undefined,
      field_name: fieldName || undefined,
      state: state || undefined,
      outcome: outcome || undefined,
      reviewed_after: reviewedAfter || undefined,
      reviewed_before: reviewedBefore || undefined,
    })
      .then((response) => {
        if (!active) return;
        setData(response);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load truth entries");
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [
    search,
    fileMd5,
    docType,
    claimId,
    reviewer,
    runId,
    fieldName,
    state,
    outcome,
    reviewedAfter,
    reviewedBefore,
  ]);

  const docTypeOptions = useMemo(() => {
    const types = new Set<string>();
    data.entries.forEach((entry) => {
      entry.doc_instances.forEach((doc) => types.add(doc.doc_type));
    });
    return Array.from(types).sort();
  }, [data.entries]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Ground Truth</h2>
          <p className="text-sm text-muted-foreground">
            Canonical truth entries with per-run extraction comparisons.
          </p>
        </div>
        <div className="text-sm text-muted-foreground">
          {loading ? "Loading…" : `${data.entries.length} entries`}
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            placeholder="Search file_md5 / doc / claim / filename"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm font-mono"
            placeholder="File MD5 (exact)"
            value={fileMd5}
            onChange={(event) => setFileMd5(event.target.value)}
          />
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            placeholder="Claim ID"
            value={claimId}
            onChange={(event) => setClaimId(event.target.value)}
          />
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            placeholder="Reviewer"
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
          />
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            type="date"
            value={reviewedAfter}
            onChange={(event) => setReviewedAfter(event.target.value)}
          />
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            type="date"
            value={reviewedBefore}
            onChange={(event) => setReviewedBefore(event.target.value)}
          />
          <input
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            placeholder="Field name"
            value={fieldName}
            onChange={(event) => setFieldName(event.target.value)}
          />
          <select
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            value={docType}
            onChange={(event) => setDocType(event.target.value)}
          >
            <option value="">All doc types</option>
            {docTypeOptions.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <select
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            value={runId}
            onChange={(event) => setRunId(event.target.value)}
          >
            <option value="">All runs</option>
            {availableRuns.map((run) => (
              <option key={run} value={run}>{run}</option>
            ))}
          </select>
          <select
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            value={state}
            onChange={(event) => setState(event.target.value)}
          >
            <option value="">All states</option>
            <option value="LABELED">LABELED</option>
            <option value="UNVERIFIABLE">UNVERIFIABLE</option>
            <option value="UNLABELED">UNLABELED</option>
            <option value="CONFIRMED">CONFIRMED</option>
          </select>
          <select
            className="w-full rounded-lg border border-input bg-background text-foreground px-3 py-2 text-sm"
            value={outcome}
            onChange={(event) => setOutcome(event.target.value as OutcomeFilter)}
          >
            <option value="">All outcomes</option>
            <option value="correct">Correct</option>
            <option value="incorrect">Incorrect</option>
            <option value="missing">Missing</option>
            <option value="unverifiable">Unverifiable</option>
            <option value="unlabeled">Unlabeled</option>
          </select>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <div className="space-y-4">
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading truth entries…</div>
        ) : data.entries.length === 0 ? (
          <div className="text-sm text-muted-foreground">No truth entries found.</div>
        ) : (
          data.entries.map((entry) => (
            <TruthEntryCard
              key={entry.file_md5}
              entry={entry}
              runs={data.runs}
              onOpenDoc={(docId, claimId) => navigate(`/claims/${claimId}/review?doc=${docId}`)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function TruthEntryCard({
  entry,
  runs,
  onOpenDoc,
}: {
  entry: TruthEntry;
  runs: string[];
  onOpenDoc: (docId: string, claimId: string) => void;
}) {
  const runsToShow = runs.filter((run) =>
    entry.fields.some((field) => field.runs && field.runs[run])
  );
  const primaryDoc = entry.source_doc_ref?.doc_id
    ? entry.doc_instances.find((doc) => doc.doc_id === entry.source_doc_ref?.doc_id)
    : entry.doc_instances[0];

  return (
    <details className="bg-card border border-border rounded-xl shadow-sm">
      <summary className="cursor-pointer select-none px-4 py-3 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="text-sm font-semibold text-foreground">
            {entry.source_doc_ref?.original_filename || primaryDoc?.original_filename || "Untitled document"}
          </div>
          <div className="text-xs text-muted-foreground">
            file_md5: <span className="font-mono">{entry.file_md5}</span>
          </div>
          <div className="text-xs text-muted-foreground">
            {entry.doc_instances.map((doc) => doc.doc_type).filter(Boolean).join(", ") || "unknown doc type"}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <div>
            Reviewer: <span className="text-foreground">{entry.review?.reviewer || "—"}</span>
          </div>
          <div>
            Reviewed: <span className="text-foreground">{entry.review?.reviewed_at || "—"}</span>
          </div>
          <div>
            Fields: <span className="text-foreground">{entry.fields.length}</span>
          </div>
          {primaryDoc ? (
            <button
              type="button"
              className="px-3 py-1 rounded-md bg-primary text-primary-foreground text-xs"
              onClick={(event) => {
                event.preventDefault();
                onOpenDoc(primaryDoc.doc_id, primaryDoc.claim_id);
              }}
            >
              Open doc
            </button>
          ) : null}
        </div>
      </summary>
      <div className="border-t border-border px-4 py-4 space-y-4">
        {entry.review?.notes ? (
          <div className="text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">Notes:</span> {entry.review.notes}
          </div>
        ) : null}
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="text-xs uppercase text-muted-foreground border-b border-border">
              <tr>
                <th className="text-left py-2 pr-4">Field</th>
                <th className="text-left py-2 pr-4">State</th>
                <th className="text-left py-2 pr-4">Truth</th>
                {runsToShow.map((run) => (
                  <th key={run} className="text-left py-2 pr-4 whitespace-nowrap">
                    {run}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entry.fields.map((field) => (
                <tr key={field.field_name} className="border-b border-border last:border-b-0">
                  <td className="py-2 pr-4 font-medium text-foreground">{field.field_name}</td>
                  <td className="py-2 pr-4 text-muted-foreground">{field.state || "—"}</td>
                  <td className="py-2 pr-4 text-foreground">{field.truth_value ?? "—"}</td>
                  {runsToShow.map((run) => {
                    const runValue = field.runs?.[run];
                    if (!runValue) {
                      return <td key={run} className="py-2 pr-4 text-muted-foreground/50">—</td>;
                    }
                    const outcome = runValue.outcome;
                    const tone =
                      outcome === "correct"
                        ? "text-emerald-600 dark:text-emerald-400"
                        : outcome === "incorrect"
                          ? "text-red-600 dark:text-red-400"
                          : outcome === "missing"
                            ? "text-amber-600 dark:text-amber-400"
                            : "text-muted-foreground";
                    return (
                      <td key={run} className="py-2 pr-4">
                        <div className="text-foreground">{runValue.normalized_value ?? runValue.value ?? "—"}</div>
                        <div className={`text-xs ${tone}`}>{outcome || "—"}</div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {entry.doc_instances.length > 0 ? (
          <div className="text-xs text-muted-foreground">
            Instances: {entry.doc_instances.map((doc) => `${doc.claim_id}/${doc.doc_id}`).join(", ")}
          </div>
        ) : null}
      </div>
    </details>
  );
}
