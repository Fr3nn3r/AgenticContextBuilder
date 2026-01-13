import { useMemo, useState } from "react";
import { cn } from "../lib/utils";

type Stage = "ingest" | "classify" | "extract";
type RunStatus = "running" | "success" | "partial" | "failed" | "queued";

interface ClaimOption {
  claim_id: string;
  doc_count: number;
}

interface RecentRun {
  run_id: string;
  status: RunStatus;
  classifier_model: string;
  extractor_model: string;
  prompt_version: string;
  claims_count: number;
  docs_processed: number;
  started_at: string;
  completed_at?: string;
  stage_progress: [number, number, number];
  last_log: string;
  errors: string[];
  claims: string[];
  timings: { ingest: string; classify: string; extract: string };
  reuse: { ingestion: number; classification: number };
}

const CLAIM_OPTIONS: ClaimOption[] = [
  { claim_id: "claim_001", doc_count: 6 },
  { claim_id: "claim_002", doc_count: 3 },
  { claim_id: "claim_003", doc_count: 9 },
];

const RECENT_RUNS: RecentRun[] = [
  {
    run_id: "run_20260112_120000_abc1234",
    status: "success",
    classifier_model: "gpt-4o",
    extractor_model: "gpt-4o-mini",
    prompt_version: "generic_extraction_v1",
    claims_count: 3,
    docs_processed: 18,
    started_at: "2026-01-12 12:00",
    completed_at: "2026-01-12 12:04",
    stage_progress: [100, 100, 89],
    last_log: "extract: 16/18 docs processed",
    errors: [
      "doc_003 · extraction · Missing required field: policy_number",
      "doc_012 · classification · Timeout contacting model",
    ],
    claims: ["claim_001 · 6 docs", "claim_002 · 3 docs", "claim_003 · 9 docs"],
    timings: { ingest: "1m 12s", classify: "38s", extract: "2m 10s" },
    reuse: { ingestion: 6, classification: 4 },
  },
  {
    run_id: "run_20260111_090000_def5678",
    status: "partial",
    classifier_model: "gpt-4o",
    extractor_model: "gpt-4o-mini",
    prompt_version: "generic_extraction_v1",
    claims_count: 2,
    docs_processed: 7,
    started_at: "2026-01-11 09:00",
    completed_at: "2026-01-11 09:02",
    stage_progress: [100, 100, 40],
    last_log: "extract: 3/7 docs processed",
    errors: ["doc_221 · extraction · OCR confidence below threshold"],
    claims: ["claim_010 · 4 docs", "claim_011 · 3 docs"],
    timings: { ingest: "42s", classify: "21s", extract: "1m 04s" },
    reuse: { ingestion: 0, classification: 0 },
  },
  {
    run_id: "run_20260113_081500_xyz9001",
    status: "running",
    classifier_model: "gpt-4o",
    extractor_model: "gpt-4o-mini",
    prompt_version: "generic_extraction_v1",
    claims_count: 4,
    docs_processed: 5,
    started_at: "2026-01-13 08:15",
    stage_progress: [100, 60, 20],
    last_log: "classify: 9/15 docs processed",
    errors: [],
    claims: ["claim_020 · 5 docs", "claim_021 · 4 docs", "claim_022 · 3 docs", "claim_023 · 3 docs"],
    timings: { ingest: "48s", classify: "ongoing", extract: "ongoing" },
    reuse: { ingestion: 2, classification: 1 },
  },
  {
    run_id: "run_20260113_082200_pend001",
    status: "queued",
    classifier_model: "gpt-4o-mini",
    extractor_model: "gpt-4o-mini",
    prompt_version: "generic_extraction_v1",
    claims_count: 1,
    docs_processed: 0,
    started_at: "2026-01-13 08:22",
    stage_progress: [0, 0, 0],
    last_log: "queued · waiting for capacity",
    errors: [],
    claims: ["claim_030 · 2 docs"],
    timings: { ingest: "-", classify: "-", extract: "-" },
    reuse: { ingestion: 0, classification: 0 },
  },
  {
    run_id: "run_20260110_150000_zzu001",
    status: "failed",
    classifier_model: "gpt-4o",
    extractor_model: "gpt-4o-mini",
    prompt_version: "generic_extraction_v1",
    claims_count: 2,
    docs_processed: 4,
    started_at: "2026-01-10 15:00",
    completed_at: "2026-01-10 15:03",
    stage_progress: [100, 30, 0],
    last_log: "classify: API rate limit exceeded",
    errors: ["doc_402 · classification · Rate limit exceeded"],
    claims: ["claim_040 · 3 docs", "claim_041 · 2 docs"],
    timings: { ingest: "33s", classify: "1m 10s", extract: "-" },
    reuse: { ingestion: 0, classification: 0 },
  },
];

const DEFAULT_STAGES: Stage[] = ["ingest", "classify", "extract"];

export function PipelineControlCenter() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [panelRunId, setPanelRunId] = useState<string | null>(null);
  const [panelView, setPanelView] = useState<"files" | "prompt">("files");
  const [selectedClaims, setSelectedClaims] = useState<string[]>([]);
  const [stages, setStages] = useState<Stage[]>(DEFAULT_STAGES);
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [computeMetrics, setComputeMetrics] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState("24h");
  const [stageFilter, setStageFilter] = useState("all");
  const [sortColumn, setSortColumn] = useState<"run" | "status" | "stages" | "started" | "completed">("started");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  const filteredClaims = useMemo(() => {
    if (!search.trim()) return CLAIM_OPTIONS;
    const q = search.toLowerCase();
    return CLAIM_OPTIONS.filter((c) => c.claim_id.toLowerCase().includes(q));
  }, [search]);

  const filteredRuns = useMemo(() => {
    let runs = RECENT_RUNS;
    if (statusFilter !== "all") {
      runs = runs.filter((run) => run.status === statusFilter);
    }
    if (stageFilter !== "all") {
      const stageIndex = stageFilter === "ingest" ? 0 : stageFilter === "classify" ? 1 : 2;
      runs = runs.filter((run) => run.stage_progress[stageIndex] < 100);
    }
    if (timeFilter !== "all") {
      // Mock filter placeholder (no real dates): keep all
    }
    const direction = sortDirection === "asc" ? 1 : -1;
    const sorted = [...runs].sort((a, b) => {
      const getValue = (run: RecentRun) => {
        if (sortColumn === "run") return run.run_id;
        if (sortColumn === "status") return run.status;
        if (sortColumn === "stages") return run.stage_progress.reduce((sum, v) => sum + v, 0);
        if (sortColumn === "completed") return run.completed_at || "";
        return run.started_at || "";
      };
      const aVal = getValue(a);
      const bVal = getValue(b);
      if (aVal < bVal) return -1 * direction;
      if (aVal > bVal) return 1 * direction;
      return 0;
    });
    return sorted;
  }, [statusFilter, stageFilter, timeFilter, sortColumn, sortDirection]);

  function toggleSort(column: "run" | "status" | "stages" | "started" | "completed") {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection("desc");
  }

  const selectedDocCount = selectedClaims
    .map((id) => CLAIM_OPTIONS.find((c) => c.claim_id === id)?.doc_count || 0)
    .reduce((sum, count) => sum + count, 0);

  const canStartRun = selectedClaims.length > 0 && stages.length > 0;

  function toggleClaim(claimId: string) {
    setSelectedClaims((prev) =>
      prev.includes(claimId) ? prev.filter((id) => id !== claimId) : [...prev, claimId]
    );
  }

  function toggleStage(stage: Stage) {
    setStages((prev) =>
      prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage]
    );
  }

  function applyPreset(preset: "full" | "classify_extract" | "extract_only") {
    if (preset === "full") setStages(["ingest", "classify", "extract"]);
    if (preset === "classify_extract") setStages(["classify", "extract"]);
    if (preset === "extract_only") setStages(["extract"]);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">Admin-only operations console</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded bg-gray-100 text-gray-600">env: local</span>
          <span className="px-2 py-1 rounded bg-red-100 text-red-700">admin</span>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-3 gap-4 p-6">
        <section className="bg-white border rounded-lg p-4 flex flex-col gap-4 xl:col-span-2">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-medium text-gray-900">Run Fleet</h2>
              <p className="text-sm text-gray-500">Live status across all runs</p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="border rounded px-2 py-1 text-xs bg-white"
              >
                <option value="all">Status: all</option>
                <option value="running">Status: running</option>
                <option value="queued">Status: queued</option>
                <option value="success">Status: success</option>
                <option value="partial">Status: partial</option>
                <option value="failed">Status: failed</option>
              </select>
              <select
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
                className="border rounded px-2 py-1 text-xs bg-white"
              >
                <option value="all">Stage: all</option>
                <option value="ingest">Stage: ingest</option>
                <option value="classify">Stage: classify</option>
                <option value="extract">Stage: extract</option>
              </select>
              <select
                value={timeFilter}
                onChange={(e) => setTimeFilter(e.target.value)}
                className="border rounded px-2 py-1 text-xs bg-white"
              >
                <option value="24h">Last 24h</option>
                <option value="7d">Last 7d</option>
                <option value="30d">Last 30d</option>
                <option value="all">All time</option>
              </select>
              <button className="px-3 py-1.5 border rounded-md text-sm">Refresh</button>
            </div>
          </div>

          <div className="overflow-auto border rounded-md">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="text-left px-3 py-2">
                    <button onClick={() => toggleSort("run")} className="underline">
                      Run
                    </button>
                  </th>
                  <th className="text-left px-3 py-2">
                    <button onClick={() => toggleSort("status")} className="underline">
                      Status
                    </button>
                  </th>
                  <th className="text-left px-3 py-2">
                    <button onClick={() => toggleSort("stages")} className="underline">
                      Stages
                    </button>
                  </th>
                  <th className="text-left px-3 py-2">
                    <button onClick={() => toggleSort("started")} className="underline">
                      Started
                    </button>
                  </th>
                  <th className="text-left px-3 py-2">
                    <button onClick={() => toggleSort("completed")} className="underline">
                      Completed
                    </button>
                  </th>
                  <th className="text-left px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
              {filteredRuns.map((run) => {
                const isOpen = selectedRunId === run.run_id;
                return (
                  <>
                    <tr
                      key={run.run_id}
                      className={cn("border-t cursor-pointer", isOpen && "bg-blue-50")}
                      onClick={() => setSelectedRunId(isOpen ? null : run.run_id)}
                    >
                      <td className="px-3 py-2 font-medium">{run.run_id}</td>
                      <td className="px-3 py-2">{run.status}</td>
                      <td className="px-3 py-2">
                        <div className="space-y-1">
                          {run.stage_progress.map((pct, idx) => (
                            <div key={idx} className="h-1 bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full bg-green-500" style={{ width: `${pct}%` }} />
                            </div>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2">{run.started_at}</td>
                      <td className="px-3 py-2">{run.completed_at || "-"}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-2">
                          <button className="underline">Open</button>
                          <button className="underline text-red-600">Delete</button>
                          {run.status === "running" || run.status === "queued" ? (
                            <button className="underline">Cancel</button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr key={`${run.run_id}-details`} className="border-t bg-white">
                        <td colSpan={7} className="px-3 py-4">
                          <div className="grid grid-cols-3 gap-4 text-xs text-gray-600">
                            <div className="border rounded-md p-3">
                              <div className="text-gray-400 mb-2">Models</div>
                              <div>Classifier: {run.classifier_model}</div>
                              <div>Extractor: {run.extractor_model}</div>
                              <div>Prompt: {run.prompt_version}</div>
                            </div>
                            <div className="border rounded-md p-3">
                              <div className="text-gray-400 mb-2">Stage timings</div>
                              <div>Ingest: {run.timings.ingest}</div>
                              <div>Classify: {run.timings.classify}</div>
                              <div>Extract: {run.timings.extract}</div>
                            </div>
                            <div className="border rounded-md p-3">
                              <div className="text-gray-400 mb-2">Reuse</div>
                              <div>Ingestion reused: {run.reuse.ingestion}</div>
                              <div>Classification reused: {run.reuse.classification}</div>
                            </div>
                          </div>

                          <div className="mt-4 grid grid-cols-2 gap-4 text-xs text-gray-600">
                            <div className="border rounded-md p-3">
                              <div className="text-gray-400 mb-2">Claims</div>
                              <ul className="space-y-1">
                                {run.claims.map((claim) => (
                                  <li key={claim}>{claim}</li>
                                ))}
                              </ul>
                            </div>
                            <div className="border rounded-md p-3">
                              <div className="text-gray-400 mb-2">Errors</div>
                              {run.errors.length === 0 ? (
                                <div>No errors</div>
                              ) : (
                                <ul className="space-y-1">
                                  {run.errors.map((err) => (
                                    <li key={err}>{err}</li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          </div>

                          <div className="mt-4 border rounded-md p-3 text-xs text-gray-600">
                            <div className="text-gray-400 mb-2">Live logs</div>
                            <div className="space-y-1">
                              <div>{run.last_log}</div>
                              <div>ingest: 18/18 docs processed</div>
                              <div>classify: 12/18 docs processed</div>
                            </div>
                          </div>

                          <div className="mt-4 flex flex-wrap gap-2 text-xs">
                            {["manifest.json", "summary.json", "metrics.json", "run.log"].map((item) => (
                              <button key={item} className="px-2 py-1 border rounded-md text-gray-600">
                                {item}
                              </button>
                            ))}
                            <button
                              className="px-2 py-1 border rounded-md text-gray-600"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPanelRunId(run.run_id);
                                setPanelView("files");
                              }}
                            >
                              View files
                            </button>
                            <button
                              className="px-2 py-1 border rounded-md text-gray-600"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPanelRunId(run.run_id);
                                setPanelView("prompt");
                              }}
                            >
                              View prompt
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

        <section className="bg-white border rounded-lg p-4 flex flex-col gap-4">
          <h2 className="text-lg font-medium text-gray-900">Run Config</h2>

          <div>
            <label className="text-sm font-medium text-gray-700">Claims</label>
            <div className="mt-2">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search claims..."
                className="w-full px-3 py-2 text-sm border rounded-md"
              />
              <div className="mt-2 space-y-2 max-h-48 overflow-auto border rounded-md p-2">
                {filteredClaims.map((claim) => (
                  <label key={claim.claim_id} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedClaims.includes(claim.claim_id)}
                        onChange={() => toggleClaim(claim.claim_id)}
                      />
                      <span>{claim.claim_id}</span>
                    </div>
                    <span className="text-gray-500">{claim.doc_count} docs</span>
                  </label>
                ))}
                {filteredClaims.length === 0 && (
                  <div className="text-xs text-gray-500 px-2 py-1">No claims match.</div>
                )}
              </div>
              <div className="mt-1 text-xs text-gray-500">
                Selected: {selectedClaims.length} claims · {selectedDocCount} docs
              </div>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700">Stages</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {(["ingest", "classify", "extract"] as Stage[]).map((stage) => (
                <button
                  key={stage}
                  onClick={() => toggleStage(stage)}
                  className={cn(
                    "px-3 py-1.5 rounded border text-sm",
                    stages.includes(stage)
                      ? "bg-gray-900 text-white border-gray-900"
                      : "bg-white text-gray-700 border-gray-200"
                  )}
                >
                  {stage}
                </button>
              ))}
            </div>
            <div className="mt-2 flex gap-2 text-xs text-gray-500">
              <button onClick={() => applyPreset("full")} className="underline">
                Full
              </button>
              <button onClick={() => applyPreset("classify_extract")} className="underline">
                Classify + Extract
              </button>
              <button onClick={() => applyPreset("extract_only")} className="underline">
                Extract Only
              </button>
            </div>
            {stages.includes("extract") && !stages.includes("classify") && (
              <div className="mt-2 text-xs text-amber-600">
                Extract‑only runs require existing classification outputs.
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3">
            <div className="border rounded-md p-3 text-xs text-gray-600">
              <div className="text-gray-400 mb-2">Prompt Template</div>
              <div>Version: generic_extraction_v1</div>
              <div>Model: gpt-4o (from prompt config)</div>
              <button
                className="mt-2 underline text-xs"
                onClick={() => {
                  setPanelRunId(selectedRunId || RECENT_RUNS[0]?.run_id || null);
                  setPanelView("prompt");
                }}
              >
                View prompt template
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={forceOverwrite}
                onChange={(e) => setForceOverwrite(e.target.checked)}
              />
              Force overwrite
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={computeMetrics}
                onChange={(e) => setComputeMetrics(e.target.checked)}
              />
              Compute metrics
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
              Dry run
            </label>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              className={cn(
                "px-4 py-2 rounded-md text-sm",
                canStartRun
                  ? "bg-gray-900 text-white"
                  : "bg-gray-200 text-gray-500 cursor-not-allowed"
              )}
              disabled={!canStartRun}
            >
              Start Run
            </button>
            <button className="px-4 py-2 rounded-md border text-sm">Preview</button>
            <button className="px-4 py-2 rounded-md border text-sm">Reset</button>
          </div>

          <div className="border rounded-md p-3 text-xs text-gray-600">
            <div className="text-gray-400 mb-2">Audit trail (latest)</div>
            <ul className="space-y-1">
              <li>22:12 · admin · started run_20260112_120000_abc1234</li>
              <li>22:08 · admin · deleted run_20260110_150000_zzz0001</li>
              <li>21:59 · admin · cancelled run_20260111_090000_def5678</li>
            </ul>
          </div>
        </section>
      </div>

      {/* Inline expanded details are rendered in the table */}

      {/* Sliding panel for files/prompt */}
      {panelRunId && (
        <div className="fixed top-0 right-0 h-full w-full max-w-md bg-white border-l shadow-xl p-4 overflow-auto">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-medium text-gray-900">Run Assets</h3>
              <p className="text-xs text-gray-500">{panelRunId}</p>
            </div>
            <button
              className="text-sm text-gray-500"
              onClick={() => setPanelRunId(null)}
            >
              Close
            </button>
          </div>

          <div className="mt-4 flex gap-2 text-xs">
            <button
              className={cn(
                "px-2 py-1 border rounded-md",
                panelView === "files" ? "bg-gray-900 text-white" : "text-gray-600"
              )}
              onClick={() => setPanelView("files")}
            >
              Files
            </button>
            <button
              className={cn(
                "px-2 py-1 border rounded-md",
                panelView === "prompt" ? "bg-gray-900 text-white" : "text-gray-600"
              )}
              onClick={() => setPanelView("prompt")}
            >
              Prompt
            </button>
          </div>

          {panelView === "files" ? (
            <div className="mt-4 text-xs text-gray-600 space-y-2">
              {["manifest.json", "summary.json", "metrics.json", "run.log", "context/", "extraction/"].map((item) => (
                <div key={item} className="flex items-center justify-between border rounded-md p-2">
                  <span>{item}</span>
                  <button className="underline">Open</button>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 text-xs text-gray-600">
              <div className="text-gray-400 mb-2">Prompt template</div>
              <pre className="whitespace-pre-wrap bg-gray-50 border rounded-md p-3 text-xs">
{`name: generic_extraction_v1
model: gpt-4o
temperature: 0.2
max_tokens: 4096
---
SYSTEM:
You are an extraction engine. Return JSON that matches the schema.
USER:
Extract the required fields with evidence from the document pages.
`}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
