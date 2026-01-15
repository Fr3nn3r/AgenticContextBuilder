# ContextBuilder Codebase Onboarding Guide

> **For New Engineers** - A comprehensive guide to understanding the insurance claims document processing pipeline.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture at a Glance](#2-architecture-at-a-glance)
3. [Backend Package Reference](#3-backend-package-reference)
4. [Frontend Package Reference](#4-frontend-package-reference)
5. [Core Data Models](#5-core-data-models)
6. [Data Flow & Pipelines](#6-data-flow--pipelines)
7. [File System Layout](#7-file-system-layout)
8. [Key Workflows](#8-key-workflows)
9. [Getting Started Checklist](#9-getting-started-checklist)

---

## 1. System Overview

### What This System Does

ContextBuilder is an **insurance claims document processing pipeline** that:

1. **Ingests** documents (PDF/image/text) via Azure Document Intelligence or OpenAI Vision
2. **Classifies** document types using LLM-based routing (LOB-agnostic)
3. **Extracts** structured fields with provenance (source location tracking)
4. **Quality gates** extraction results (pass/warn/fail)
5. **QA Console** for human labeling and ground truth management
6. **Compliance logging** for audit trails and reproducibility

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.9+, FastAPI, Pydantic |
| **Frontend** | React 18, TypeScript, Tailwind CSS, Vite |
| **AI/ML** | OpenAI GPT-4, Azure Document Intelligence |
| **Storage** | File-based JSON (no database) |
| **Real-time** | WebSockets for pipeline progress |

### Supported Document Types

```
fnol_form          - First Notice of Loss forms
insurance_policy   - Policy documents
police_report      - Accident/incident reports
invoice            - Repair/service invoices
id_document        - ID cards, passports
vehicle_registration - Vehicle papers
certificate        - Various certificates
medical_report     - Medical documentation
travel_itinerary   - Travel booking docs
customer_comm      - Customer correspondence
supporting_document - Miscellaneous supporting docs
damage_evidence    - Photos/evidence of damage
```

---

## 2. Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                 │
│   Documents (PDF/Image/Text) → CLI or API Upload                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE STAGES                                │
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │  INGESTION  │───▶│CLASSIFICATION│───▶│ EXTRACTION  │───▶│ QUALITY  │ │
│  │             │    │             │    │             │    │   GATE   │ │
│  │ Azure DI    │    │ LLM Router  │    │ LLM + Specs │    │Pass/Warn │ │
│  │ OpenAI Vis  │    │ Doc Type    │    │ Field Rules │    │  /Fail   │ │
│  │ Tesseract   │    │ Detection   │    │ Provenance  │    │          │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                                 │
│                                                                          │
│   output/claims/{claim_id}/                                             │
│     ├── docs/{doc_id}/          # Per-document storage                  │
│     │   ├── source/             # Original files                        │
│     │   ├── text/pages.json     # OCR text                             │
│     │   └── labels/latest.json  # Human labels                         │
│     └── runs/{run_id}/          # Batch extraction results             │
│         └── extraction/{doc_id}.json                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                              │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  QA Console  │  │   Pipeline   │  │   Metrics    │  │ Compliance  │ │
│  │  (Labeling)  │  │   Control    │  │  Dashboard   │  │   Audit     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
│                                                                          │
│                     React + TypeScript + Tailwind                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Dependency Flow

```
CLI/API Request
    │
    ▼
pipeline/run.py (orchestration)
    │
    ├──▶ impl/azure_di_ingestion.py (or openai_vision, tesseract)
    │         │
    │         ▼
    │    pipeline/text.py (page normalization)
    │
    ├──▶ classification/openai_classifier.py
    │         │
    │         ▼
    │    services/llm_audit.py (logging)
    │
    ├──▶ extraction/extractors/generic.py
    │         │
    │         ├──▶ extraction/spec_loader.py (YAML specs)
    │         └──▶ extraction/normalizers.py (value normalization)
    │
    └──▶ storage/filesystem.py (persistence)
              │
              ▼
         services/decision_ledger.py (compliance)
```

---

## 3. Backend Package Reference

### Package Overview

```
src/context_builder/
├── api/                 # FastAPI REST endpoints + services
├── pipeline/            # Core orchestration & stages
├── classification/      # Document type routing
├── extraction/          # Field extraction engine
├── impl/                # Ingestion implementations
├── storage/             # Filesystem persistence & indexing
├── schemas/             # Pydantic data models
├── services/            # Business logic & compliance
├── utils/               # Shared utilities
├── prompts/             # LLM prompt templates
├── ingestion.py         # Ingestion abstractions
└── cli.py               # Command-line interface
```

---

### 3.1 `api/` - FastAPI Backend & Services

**Purpose**: HTTP API endpoints and business services for the QA Console UI.

| File | Responsibility |
|------|----------------|
| `main.py` | FastAPI app setup, all route definitions, WebSocket handlers. Entry point for the backend server. |
| `models.py` | Pydantic request/response models (`ClaimSummary`, `DocPayload`, `SaveLabelsRequest`, etc.) |
| `insights.py` | Analytics calculations (accuracy rates, field coverage, error analysis) |

#### `api/services/` - Service Layer

| File | Responsibility |
|------|----------------|
| `pipeline.py` | Async pipeline orchestration with real-time progress broadcasting via WebSocket |
| `claims.py` | List claims, calculate risk scores, retrieve run summaries |
| `documents.py` | Document retrieval, content formatting, PDF/image access |
| `labels.py` | Human label persistence with compliance decision record creation |
| `truth.py` | Ground truth management (canonical truth data by file MD5) |
| `audit.py` | Audit trail tracking (user actions, review decisions) |
| `auth.py` | Authentication service, session management, role-based access |
| `users.py` | User CRUD operations, role assignments |
| `workspace.py` | Multi-workspace support (switch between claim sets) |
| `upload.py` | Document upload handling, staging area management |
| `prompt_config.py` | Prompt template configuration CRUD |
| `insights.py` | Insights calculation wrapper service |
| `utils.py` | Common API utilities (`extract_claim_number()`, path helpers) |

---

### 3.2 `pipeline/` - Core Orchestration

**Purpose**: Pipeline stages, document discovery, state management, and orchestration.

| File | Responsibility |
|------|----------------|
| `run.py` | **Master orchestrator** - `process_claim()` and `process_document()` coordinate ingestion → classification → extraction → quality gate |
| `discovery.py` | Find claims and documents from filesystem (`discover_claims()`, `DiscoveredClaim`, `DiscoveredDocument`) |
| `paths.py` | Path structure generators (`ClaimPaths`, `DocPaths`, `RunPaths`) - defines where outputs go |
| `text.py` | Page content parsing (`build_pages_json()`, `build_pages_json_from_azure_di()`) |
| `stages.py` | Pipeline stage protocol (`Stage[T]` protocol for generic stage execution) |
| `state.py` | Claim/run state checking (`is_claim_processed()`, `get_latest_run()`) |
| `writer.py` | Result serialization (`ResultWriter` - write extraction JSON to disk) |
| `metrics.py` | Pipeline metrics calculation (field coverage, quality scores, timing) |
| `eval.py` | Evaluation against ground truth (`evaluate_run()` - compare predictions to labels) |

---

### 3.3 `classification/` - Document Type Router

**Purpose**: Route documents to correct extraction specs using LLM classification.

| File | Responsibility |
|------|----------------|
| `__init__.py` | Abstract base class `DocumentClassifier`, `ClassifierFactory` registry, exception types |
| `openai_classifier.py` | OpenAI-based classification - calls GPT-4 with optimized context, returns `DocumentClassification` |
| `context_builder.py` | Context optimization for classification - reduces token usage with smart document sampling |

**Key Flow**:
```python
classifier = ClassifierFactory.create("openai")
result = classifier.classify(text, filename)
# Returns: { doc_type: "fnol_form", confidence: 0.95, signals: [...] }
```

---

### 3.4 `extraction/` - Field Extraction Engine

**Purpose**: Extract structured fields from classified documents using specs and LLM.

| File | Responsibility |
|------|----------------|
| `base.py` | `FieldExtractor` abstract base class, `ExtractorFactory` registry, `CandidateSpan` dataclass |
| `spec_loader.py` | Load extraction specifications from YAML (`DocTypeSpec`, `FieldRule`, `get_spec()`) |
| `normalizers.py` | Field value normalization (`uppercase_trim`, `date_to_iso`, `plate_normalize`) and validators (`non_empty`, `is_date`) |
| `page_parser.py` | Parse page content structure (`ParsedPage`, `find_text_position()` for character offsets) |

#### `extraction/extractors/`

| File | Responsibility |
|------|----------------|
| `generic.py` | **Primary extractor** - Two-pass extraction: (1) find candidate spans, (2) LLM structured extraction with provenance |

#### `extraction/specs/` - YAML Configuration (SSOT)

| File | Responsibility |
|------|----------------|
| `doc_type_catalog.yaml` | **Single source of truth** for all document types and classification cues |
| `fnol_form.yaml` | Field specs for FNOL forms (required/optional fields, normalization rules, quality gate rules) |
| `invoice.yaml` | Field specs for invoices |
| `police_report.yaml` | Field specs for police reports |
| *(etc. for each doc type)* | |

---

### 3.5 `impl/` - Ingestion Implementations

**Purpose**: Concrete implementations for text extraction from different sources.

| File | Responsibility |
|------|----------------|
| `azure_di_ingestion.py` | Azure Document Intelligence API integration - calls prebuilt-layout model, returns markdown + JSON metadata |
| `openai_vision_ingestion.py` | OpenAI Vision API fallback - GPT-4V image analysis for OCR when Azure DI struggles |
| `tesseract_ingestion.py` | Local Tesseract OCR - pure Python offline OCR, no API calls (for air-gapped deployments) |

---

### 3.6 `storage/` - Data Persistence & Indexing

**Purpose**: Filesystem-based document and result storage with optional JSONL indexing.

| File | Responsibility |
|------|----------------|
| `filesystem.py` | **Main storage implementation** - `FileStorage` class with `list_claims()`, `list_docs()`, `get_doc()`, etc. |
| `protocol.py` | `Storage` protocol - abstract interface for storage backends |
| `facade.py` | `StorageFacade` convenience wrapper |
| `index_builder.py` | Generate JSONL indexes from filesystem for O(1) lookups |
| `index_reader.py` | Read and query JSONL indexes efficiently |
| `models.py` | Storage data models (`ClaimRef`, `DocRef`, `DocBundle`, `RunRef`, `LabelSummary`) |
| `truth_store.py` | Ground truth persistence (`TruthStore` - manage labeled truth by file_md5) |
| `pii_vault.py` | PII masking/redaction utilities |
| `version_bundles.py` | Version snapshot capture (git commit, model version, spec hashes for reproducibility) |

---

### 3.7 `schemas/` - Pydantic Data Models

**Purpose**: Type-safe serializable data structures for extraction results, labels, and compliance.

| File | Responsibility |
|------|----------------|
| `extraction_result.py` | `ExtractionResult`, `ExtractedField`, `FieldProvenance`, `QualityGate`, `PageContent` |
| `label.py` | `LabelResult`, `FieldLabel`, `DocLabels`, `FieldState` enum (LABELED/UNVERIFIABLE/UNLABELED) |
| `decision_record.py` | `DecisionRecord`, `DecisionType`, `VersionBundle`, `EvidenceCitation` - compliance audit trail |
| `document_classification.py` | `DocumentClassification` schema |
| `document_analysis.py` | `DocumentAnalysis` metadata |
| `run_errors.py` | `DocStatus`, `PipelineStage`, `RunErrorCode` enums |
| `llm_call_record.py` | `LLMCallRecord` - timestamp, model, usage, cost tracking |

---

### 3.8 `services/` - Business Logic & Compliance

**Purpose**: Core services for compliance logging, LLM audit trails, and decision ledgers.

| File | Responsibility |
|------|----------------|
| `llm_audit.py` | LLM call logging wrapper (`LLMAuditService`, `AuditedOpenAIClient`) |
| `decision_ledger.py` | Decision audit trail persistence (`DecisionLedger` - append-only log) |

#### `services/compliance/` - Compliance Subsystem

| File | Responsibility |
|------|----------------|
| `__init__.py` | Lazy-loaded compliance module exports |
| `config.py` | `ComplianceStorageConfig`, `StorageBackendType` enum |
| `interfaces.py` | `DecisionStorage`, `LLMCallStorage` protocol interfaces |
| `factories.py` | `DecisionRecordFactory` - create records with automatic hashing |
| `storage_factory.py` | Backend selection based on config |
| `crypto.py` | Encryption utilities (AES-256-GCM, lazy-loaded) |
| `file/decision_storage.py` | File-based decision storage with hash chain verification |
| `file/llm_storage.py` | File-based LLM call audit log (JSONL format) |
| `encrypted/` | Encrypted file storage variants |

---

### 3.9 `utils/` - Utility Functions

**Purpose**: Reusable helper functions across the codebase.

| File | Responsibility |
|------|----------------|
| `prompt_loader.py` | Load prompt templates (`load_prompt()` - parse markdown with YAML frontmatter, render Jinja2) |
| `filename_utils.py` | File naming helpers (`sanitize_filename()`, `extract_claim_from_path()`) |
| `file_utils.py` | File operations (`get_file_metadata()`) |
| `hashing.py` | MD5 hashing for content-based IDs |
| `schema_renderer.py` | Render extraction specs to prompt format for LLM context |
| `symbol_table_renderer.py` | Render extracted fields as symbol table |
| `json_logic_transpiler.py` | Quality gate rule evaluation |
| `udm_bridge.py` | Universal Data Model integration for field mapping |

---

### 3.10 `cli.py` - Command-Line Interface

**Purpose**: Standalone batch processing without API server.

**Commands**:
```bash
# Ingest documents (OCR/text extraction)
python -m context_builder.cli acquire -p azure-di -o output/claims input/

# Classify document types
python -m context_builder.cli classify -o output/claims

# Extract fields
python -m context_builder.cli extract -o output/claims --model gpt-4o

# Full pipeline
python -m context_builder.cli pipeline -o output/claims input/

# Evaluate against ground truth
python -m context_builder.cli evaluate -o output/claims
```

---

## 4. Frontend Package Reference

### Package Overview

```
ui/src/
├── api/                 # API client layer
├── components/          # React UI components
├── context/             # React Context (Auth)
├── hooks/               # Custom React hooks
├── lib/                 # Shared utilities
├── pages/               # Page-level components
├── test/                # Test fixtures
├── types/               # TypeScript definitions
├── App.tsx              # Root router
├── main.tsx             # Entry point
└── index.css            # Global Tailwind styles
```

---

### 4.1 `api/` - API Client

| File | Responsibility |
|------|----------------|
| `client.ts` | **Main API client** - 50+ functions for all backend endpoints. Handles auth token injection, 401 redirects, caching. Organized by domain: Claims, Runs, Insights, Classification, Upload, Pipeline, Compliance. |

**Key Functions**:
```typescript
// Claims & Documents
listClaims(), listDocs(claimId), getDoc(docId, claimId, runId)
saveLabels(docId, claimId, labels)

// Pipeline
startPipeline(config), cancelPipeline(batchId), getPipelineStatus(batchId)

// Insights
getInsightsOverview(), getInsightsPriorities(), getInsightsExamples()

// Compliance
verifyDecisionLedger(), listDecisions(), listVersionBundles()
```

---

### 4.2 `types/index.ts` - Type Definitions

**Single source of truth** for all TypeScript interfaces.

| Category | Key Types |
|----------|-----------|
| **Claims/Docs** | `ClaimSummary`, `DocSummary`, `DocPayload`, `PageContent` |
| **Extraction** | `ExtractedField`, `FieldProvenance`, `ExtractionResult`, `QualityGate` |
| **Labels** | `FieldLabel`, `FieldState`, `UnverifiableReason`, `LabelResult`, `DocLabels` |
| **Classification** | `ClassificationDoc`, `ClassificationDetail`, `DocTypeCatalogEntry` |
| **Pipeline** | `PipelineBatch`, `DocProgress`, `DocPipelinePhase`, `WebSocketMessage` |
| **Insights** | `InsightsOverview`, `DocTypeMetrics`, `PriorityItem`, `FieldDetails` |
| **Compliance** | `DecisionRecord`, `VerificationResult`, `VersionBundle` |

---

### 4.3 `context/` - React Context

| File | Responsibility |
|------|----------------|
| `AuthContext.tsx` | Role-based access control provider. Roles: `admin`, `reviewer`, `operator`, `auditor`. Provides `login()`, `logout()`, `canAccess()`, `canEdit()`, session management. |

**Permission Matrix**:
| Role | Access |
|------|--------|
| Admin | Everything |
| Reviewer | Documents, classification, labels, ground truth |
| Operator | Pipeline, claims, new claims |
| Auditor | Compliance, pipeline status (read-only) |

---

### 4.4 `hooks/` - Custom Hooks

| File | Responsibility |
|------|----------------|
| `usePipelineData.ts` | Data fetching hooks: `usePipelineClaims()`, `usePipelineRuns()`, `usePromptConfigs()`, `useAuditLog()` |
| `usePipelineWebSocket.ts` | Real-time WebSocket for pipeline progress. Auto-reconnect, ping/pong keepalive, handles `doc_progress`, `batch_complete`, `batch_cancelled` messages. |

---

### 4.5 `lib/` - Utilities

| File | Responsibility |
|------|----------------|
| `formatters.ts` | Display formatting: `formatDocType()` (snake_case → Title Case), `formatFieldName()`, `formatTimestamp()`, `formatPercent()`, `formatDuration()`, `truncateBatchId()` |
| `bboxUtils.ts` | Bounding box transformations for provenance highlighting: `findWordsInRange()`, `computeBoundingBoxes()`, `transformPolygonToPixels()` |
| `chartUtils.ts` | Chart configuration utilities |
| `utils.ts` | `cn()` - Tailwind className merge (clsx + twMerge) |

---

### 4.6 `components/` - React Components

#### Core Application

| File | Responsibility |
|------|----------------|
| `App.tsx` | **Root router** - All route definitions, global state (claims, docs, filters, selected batch), sidebar navigation |
| `Sidebar.tsx` | Fixed left navigation, role-based visibility, theme switcher (light/dark, color themes), logout |
| `BatchWorkspace.tsx` | Layout container for batch-scoped routes, provides batch context to children |

#### Document & Extraction Review

| File | Responsibility |
|------|----------------|
| `DocumentReview.tsx` | **Main labeling interface** - Doc list (left), PDF/image viewer (center), FieldsTable (right). Handles provenance highlighting, keyboard shortcuts (1/2/3, n/p). |
| `FieldsTable.tsx` | Expandable field table with labeling. Shows extracted vs truth values, confidence, comparison badges. Actions: confirm, set truth, mark unverifiable. |
| `DocumentViewer.tsx` | Wrapper for PDF/image viewers, manages bounding box overlays |
| `PDFViewer.tsx` | PDF rendering with react-pdf, page navigation, zoom, bounding box overlay |
| `ImageViewer.tsx` | Image rendering for scanned documents |
| `BboxOverlay.tsx` | Renders quadrilateral polygons on canvas for provenance highlighting |

#### Claims & Batch Views

| File | Responsibility |
|------|----------------|
| `ClaimsTable.tsx` | Searchable, filterable claims table. Columns: claim_id, doc count, status, LOB, risk, last processed. |
| `ClaimReview.tsx` | Claim-level review (multiple docs per claim), navigation between claims |
| `ExtractionPage.tsx` | Batch overview dashboard - batch history, phase progress, doc type distribution, quality gate breakdown |

#### Classification Review

| File | Responsibility |
|------|----------------|
| `ClassificationReview.tsx` | Review doc type classifications, accept/override predicted types |
| `ClassificationPanel.tsx` | Panel showing classification details, confidence, signals |
| `ClassificationInfoPanel.tsx` | Detailed classification info (signals, hints, summary) |

#### Pipeline & Upload

| File | Responsibility |
|------|----------------|
| `PipelineControlCenter.tsx` | **Main pipeline interface** - Tabs: New Batch (select claims, stages, model), Batches (view all runs), Config (prompt configs) |
| `PipelineProgress.tsx` | Real-time progress via WebSocket, stage progress bars, doc-level status |
| `NewClaimPage.tsx` | Document upload - drag & drop, batch upload, file validation |
| `DocumentUploader.tsx` | Upload form component |

#### Ground Truth & Evaluation

| File | Responsibility |
|------|----------------|
| `TruthPage.tsx` | Ground truth browsing/filtering, multi-run comparison against truth |
| `EvaluationPage.tsx` | Metrics dashboard - accuracy, evidence rate, precision by field, doc type breakdown |

#### Templates & Admin

| File | Responsibility |
|------|----------------|
| `TemplatesPage.tsx` | View/edit extraction templates, JSON editor |
| `AdminPage.tsx` | User management, role assignment, workspace management |
| `WorkspaceManager.tsx` | Create/switch workspaces |
| `LoginPage.tsx` | Login form |
| `ProtectedRoute.tsx` | Route guard for auth and RBAC |

#### Shared Components (`components/shared/`)

| File | Responsibility |
|------|----------------|
| `StatusBadge.tsx` | Status indicators (Pass/Warn/Fail, Correct/Incorrect/Missing, Labeled/Unlabeled) |
| `MetricCard.tsx` | Card for metrics display with value, label, delta |
| `LoadingSkeleton.tsx` | Skeleton loaders for loading states |
| `EmptyState.tsx` | Empty state variants (NoData, NoSearchResults, SelectToView, Error) |
| `BatchContextBar.tsx` | Header showing selected batch metadata, batch selector |
| `BatchSelector.tsx` | Dropdown for batch selection |
| `BatchSubNav.tsx` | Sub-navigation tabs within batch workspace |

#### Charts (`components/charts/`)

| File | Responsibility |
|------|----------------|
| `ChartCard.tsx` | Wrapper for chart cards |
| `DonutChart.tsx` | Quality gate breakdown |
| `MetricsBarChart.tsx` | Doc type distribution |
| `RadialGauge.tsx` | Accuracy/confidence gauges |
| `TrendAreaChart.tsx` | Trend visualization |

#### Compliance Pages (`pages/compliance/`)

| File | Responsibility |
|------|----------------|
| `Overview.tsx` | Compliance dashboard - hash chain integrity, recent decisions |
| `Ledger.tsx` | Complete audit trail, filterable by decision type |
| `Verification.tsx` | Hash chain verification results |
| `VersionBundles.tsx` | Reproducibility tracking (git commits, model versions) |
| `Controls.tsx` | Configuration change history, label history |

---

### 4.7 Routing Structure

```
/login                              → LoginPage
/batches                            → BatchWorkspace (layout)
  /:batchId                         → ExtractionPage (dashboard)
  /:batchId/documents               → DocumentReview (labeling)
  /:batchId/classification          → ClassificationReview
  /:batchId/claims                  → ClaimsTable
  /:batchId/metrics                 → MetricsPage
/claims
  /new                              → NewClaimPage (upload)
  /all                              → ClaimsTable (all claims)
  /:claimId/review                  → ClaimReview
/evaluation                         → EvaluationPage
/truth                              → TruthPage
/templates                          → TemplatesPage
/pipeline                           → PipelineControlCenter
/compliance
  /                                 → ComplianceOverview
  /ledger                           → ComplianceLedger
  /verification                     → ComplianceVerification
  /version-bundles                  → ComplianceVersionBundles
  /controls                         → ComplianceControls
/admin                              → AdminPage
```

---

## 5. Core Data Models

### 5.1 ExtractionResult (Backend + Frontend)

The output of document extraction with provenance tracking.

```typescript
ExtractionResult {
  schema_version: "extraction_result_v1"

  run: {
    run_id: string              // ISO timestamp
    model: string               // "gpt-4o"
    extractor_version: string
    prompt_version: string
    input_hashes: { pdf_md5, di_text_md5 }
  }

  doc: {
    doc_id: string              // MD5 of content
    claim_id: string
    doc_type: string            // "fnol_form"
    doc_type_confidence: number // 0.0-1.0
    language: string            // "en", "es"
    page_count: number
  }

  pages: [{
    page: number                // 1-indexed
    text: string
    text_md5: string
  }]

  fields: [{
    name: string                // "event_date"
    value: string | null        // Raw extracted
    normalized_value: string    // Post-normalization
    confidence: number          // 0.0-1.0
    status: "present" | "missing" | "uncertain"
    provenance: [{
      page: number
      method: "di_text" | "vision_ocr" | "llm_parse"
      text_quote: string        // Source text
      char_start: number
      char_end: number
    }]
  }]

  quality_gate: {
    status: "pass" | "warn" | "fail"
    reasons: string[]
    missing_required_fields: string[]
  }
}
```

**Storage**: `output/claims/{claim_id}/runs/{run_id}/extraction/{doc_id}.json`

---

### 5.2 LabelResult (Human Ground Truth)

Human-provided labels independent of extraction runs.

```typescript
LabelResult {
  schema_version: "label_v3"
  doc_id: string
  claim_id: string

  review: {
    reviewed_at: datetime
    reviewer: string
    notes: string
  }

  field_labels: [{
    field_name: string
    state: "LABELED" | "UNVERIFIABLE" | "UNLABELED"
    truth_value?: string           // Required when LABELED
    unverifiable_reason?: string   // Required when UNVERIFIABLE
      // "not_present_in_doc" | "unreadable_text" | "wrong_doc_type" | "cannot_verify" | "other"
    notes: string
  }]

  doc_labels: {
    doc_type_correct: boolean
    doc_type_truth?: string        // When doc_type_correct=false
  }
}
```

**Storage**: `output/claims/{claim_id}/docs/{doc_id}/labels/latest.json`

---

### 5.3 DecisionRecord (Compliance Audit Trail)

Tamper-evident record of all system decisions.

```typescript
DecisionRecord {
  decision_id: string              // UUID
  decision_type: "classification" | "extraction" | "quality_gate" | "human_review" | "override"
  created_at: datetime

  // Linked hash chain for tamper detection
  record_hash: string              // SHA-256 of this record
  previous_hash: string            // Previous record's hash

  claim_id?: string
  doc_id?: string
  run_id?: string

  version_bundle_id?: string       // Links to reproducibility info

  rationale: {
    summary: string
    confidence: number
    rule_traces: [{ rule_name, triggered, input_values, output_value }]
    evidence_citations: [{ doc_id, page, text_quote, char_start, char_end }]
    llm_call_id?: string
  }

  outcome: {
    // Varies by decision_type
    doc_type?: string
    fields_extracted?: []
    quality_gate_status?: string
    field_corrections?: []
  }

  actor_type: "system" | "human"
  actor_id?: string
}
```

**Storage**: Compliance ledger (file-based or encrypted)

---

### 5.4 DocumentClassification

Output from the classification router stage.

```typescript
DocumentClassification {
  document_type: string           // From doc_type_catalog
  language: string
  confidence: number              // 0.0-1.0
  summary: string                 // 1-2 sentence description
  signals: string[]               // 2-5 evidence markers
  key_hints?: {                   // Optional lightweight hints
    policy_number?, claim_reference?, incident_date?,
    vehicle_plate?, invoice_number?, total_amount?, currency?
  }
}
```

---

### 5.5 Extraction Spec (YAML)

Configuration for field extraction per document type.

```yaml
# extraction/specs/fnol_form.yaml
doc_type: fnol_form
version: v1

required_fields:
  - event_date
  - loss_type

optional_fields:
  - policy_number
  - claim_number
  - claimant_name

field_rules:
  policy_number:
    normalize: uppercase_trim
    validate: non_empty
    hints: ["policy number", "confirmation number"]

  event_date:
    normalize: date_to_iso
    validate: is_date
    hints: ["date of loss", "incident date"]

quality_gate:
  pass_if:
    - required_present_ratio >= 1.0
    - evidence_rate >= 0.7
  warn_if:
    - evidence_rate < 0.7
  fail_if:
    - required_present_ratio < 1.0
```

---

## 6. Data Flow & Pipelines

### 6.1 Document Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│ INPUT: PDF/Image/Text Document                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: INGESTION                                                       │
│                                                                          │
│ impl/azure_di_ingestion.py  OR  impl/openai_vision_ingestion.py         │
│                                                                          │
│ Output: pages.json                                                       │
│ [                                                                        │
│   { "page": 1, "text": "...", "text_md5": "abc123" },                   │
│   { "page": 2, "text": "...", "text_md5": "def456" }                    │
│ ]                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: CLASSIFICATION                                                  │
│                                                                          │
│ classification/openai_classifier.py                                      │
│                                                                          │
│ Input: First ~2000 chars of text + filename                             │
│ Output: DocumentClassification                                           │
│ {                                                                        │
│   "document_type": "fnol_form",                                         │
│   "confidence": 0.95,                                                   │
│   "signals": ["claim report", "date of loss", "FNOL"]                   │
│ }                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: EXTRACTION                                                      │
│                                                                          │
│ extraction/extractors/generic.py                                         │
│ + extraction/specs/fnol_form.yaml                                        │
│                                                                          │
│ Two-Pass Process:                                                        │
│ 1. Find candidate spans in text (regex + heuristics)                    │
│ 2. LLM structured extraction with provenance                            │
│                                                                          │
│ Output: ExtractionResult with fields + provenance                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: QUALITY GATE                                                    │
│                                                                          │
│ Evaluate against spec rules:                                             │
│ - required_present_ratio >= 1.0 → PASS                                  │
│ - evidence_rate < 0.7 → WARN                                            │
│ - missing required fields → FAIL                                        │
│                                                                          │
│ Output: QualityGate { status: "pass"|"warn"|"fail" }                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STORAGE: Write Results                                                   │
│                                                                          │
│ output/claims/{claim_id}/runs/{run_id}/extraction/{doc_id}.json         │
│                                                                          │
│ + Compliance Decision Records (classification, extraction, quality_gate)│
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 6.2 Human Labeling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ QA Console: DocumentReview Component                                     │
│                                                                          │
│ ┌─────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐  │
│ │  Doc List   │  │   PDF/Image Viewer   │  │     FieldsTable         │  │
│ │             │  │                       │  │                         │  │
│ │ Filter by:  │  │  Bounding box overlay │  │ Field | Extracted | ✓  │  │
│ │ - doc_type  │  │  for provenance       │  │ ──────┼───────────┼──  │  │
│ │ - status    │  │                       │  │ date  │ 2024-01-15│ ✓  │  │
│ │ - claim     │  │  Click quote to       │  │ name  │ John Doe  │ ✗  │  │
│ │             │  │  highlight source     │  │ plate │ [missing] │ ?  │  │
│ └─────────────┘  └─────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                           User Actions:
                           1. Confirm extracted value (keyboard: 1)
                           2. Set different truth value (keyboard: 2)
                           3. Mark unverifiable (keyboard: 3)
                           4. Navigate docs (keyboard: n/p)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Save Labels: POST /api/docs/{doc_id}/labels                             │
│                                                                          │
│ {                                                                        │
│   "reviewer": "alice@company.com",                                      │
│   "field_labels": [                                                     │
│     { "field_name": "event_date", "state": "LABELED",                   │
│       "truth_value": "2024-01-15" },                                    │
│     { "field_name": "claimant_name", "state": "LABELED",                │
│       "truth_value": "Jane Doe" },                                      │
│     { "field_name": "vehicle_plate", "state": "UNVERIFIABLE",           │
│       "unverifiable_reason": "not_present_in_doc" }                     │
│   ],                                                                     │
│   "doc_labels": { "doc_type_correct": true }                            │
│ }                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Storage + Compliance                                                     │
│                                                                          │
│ 1. Write: output/claims/{claim_id}/docs/{doc_id}/labels/latest.json    │
│ 2. Create DecisionRecord (type: HUMAN_REVIEW)                           │
│ 3. Update truth registry by file_md5                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 6.3 Accuracy Calculation

```
For each LABELED field in ground truth:

  extracted_value = extraction_result.fields[field_name].normalized_value
  truth_value = label_result.field_labels[field_name].truth_value

  if extracted_value == truth_value:
      outcome = "correct"       ✓
  elif extracted_value exists but != truth_value:
      outcome = "incorrect"     ✗
  elif truth_value exists but no extraction:
      outcome = "missing"       ⚠

  accuracy_rate = correct / (correct + incorrect + missing)
```

---

## 7. File System Layout

```
project_root/
│
├── src/context_builder/           # Python backend
│   ├── api/
│   ├── pipeline/
│   ├── classification/
│   ├── extraction/
│   │   └── specs/                 # YAML field specs (SSOT)
│   ├── impl/
│   ├── storage/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   ├── prompts/                   # LLM prompt templates
│   ├── ingestion.py
│   └── cli.py
│
├── ui/                            # React frontend
│   └── src/
│       ├── api/
│       ├── components/
│       ├── context/
│       ├── hooks/
│       ├── lib/
│       ├── pages/
│       ├── types/
│       └── App.tsx
│
├── output/                        # Data storage
│   ├── claims/
│   │   └── {claim_id}/
│   │       ├── meta/
│   │       │   └── claim.json
│   │       ├── docs/
│   │       │   └── {doc_id}/
│   │       │       ├── source/
│   │       │       │   └── original.pdf
│   │       │       ├── text/
│   │       │       │   └── pages.json
│   │       │       ├── meta/
│   │       │       │   └── doc.json
│   │       │       └── labels/
│   │       │           └── latest.json
│   │       └── runs/
│   │           └── {run_id}/
│   │               └── extraction/
│   │                   └── {doc_id}.json
│   ├── runs/
│   │   └── {run_id}/
│   │       ├── manifest.json
│   │       └── eval/
│   └── registry/                  # JSONL indexes
│
├── .contextbuilder/               # Workspace config
│   ├── workspaces.json
│   └── compliance/
│       ├── ledger/
│       └── llm_calls/
│
├── tests/
│   ├── unit/
│   └── conftest.py
│
├── scripts/
│   ├── dev-restart.ps1
│   ├── kill-uvicorn.ps1
│   └── test.ps1
│
└── input/                         # Source documents
```

---

## 8. Key Workflows

### Starting the Development Environment

```bash
# Terminal 1: Backend
.\scripts\dev-restart.ps1          # Or: uvicorn context_builder.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd ui && npm run dev
```

### Running the Pipeline via CLI

```bash
# Full pipeline
python -m context_builder.cli pipeline -p azure-di -o output/claims input/

# Or step by step:
python -m context_builder.cli acquire -p azure-di -o output/claims input/
python -m context_builder.cli classify -o output/claims
python -m context_builder.cli extract -o output/claims --model gpt-4o
```

### Running the Pipeline via UI

1. Navigate to `/pipeline`
2. Select claims in "New Batch" tab
3. Choose stages (ingest, classify, extract)
4. Select model and prompt config
5. Click "Run Pipeline"
6. Watch real-time progress via WebSocket

### Labeling Documents

1. Navigate to `/batches/{batchId}/documents`
2. Select a document from the list
3. Review extracted fields in FieldsTable
4. Click provenance quotes to highlight in viewer
5. Confirm, correct, or mark unverifiable
6. Save labels

### Running Tests

```bash
.\scripts\test.ps1                 # All tests
.\scripts\test.ps1 tests/unit/     # Specific directory
.\scripts\test.ps1 -k "quality"    # Pattern matching
```

---

## 9. Getting Started Checklist

### Day 1: Understand the Domain

- [ ] Read this document end-to-end
- [ ] Understand the document types in `extraction/specs/doc_type_catalog.yaml`
- [ ] Review one extraction spec (e.g., `fnol_form.yaml`) to understand field rules
- [ ] Look at sample data in `output/claims/` (if available)

### Day 2: Trace the Pipeline

- [ ] Run the CLI pipeline on test documents
- [ ] Follow the code path: `cli.py` → `pipeline/run.py` → stages
- [ ] Understand how `DiscoveredClaim` flows through processing
- [ ] Check the output files generated

### Day 3: Explore the API

- [ ] Start the backend (`.\scripts\dev-restart.ps1`)
- [ ] Open http://localhost:8000/docs (FastAPI Swagger)
- [ ] Test key endpoints: `/api/claims`, `/api/docs/{doc_id}`
- [ ] Understand request/response models in `api/models.py`

### Day 4: Understand the Frontend

- [ ] Start the frontend (`cd ui && npm run dev`)
- [ ] Login and navigate the QA Console
- [ ] Trace `App.tsx` routes
- [ ] Understand `api/client.ts` functions
- [ ] Review `types/index.ts` for data contracts

### Day 5: Deep Dive Areas

- [ ] Classification: `classification/openai_classifier.py`
- [ ] Extraction: `extraction/extractors/generic.py`
- [ ] Storage: `storage/filesystem.py`
- [ ] Compliance: `services/compliance/`

### Day 6: Make a Small Change

- [ ] Add a new optional field to an extraction spec
- [ ] Verify it appears in extraction results
- [ ] Test the change with `.\scripts\test.ps1`

---

## Quick Reference

### Key Files to Know

| Purpose | File |
|---------|------|
| Pipeline orchestration | `src/context_builder/pipeline/run.py` |
| Document classification | `src/context_builder/classification/openai_classifier.py` |
| Field extraction | `src/context_builder/extraction/extractors/generic.py` |
| Doc type definitions | `src/context_builder/extraction/specs/doc_type_catalog.yaml` |
| API endpoints | `src/context_builder/api/main.py` |
| Storage operations | `src/context_builder/storage/filesystem.py` |
| Frontend API client | `ui/src/api/client.ts` |
| TypeScript types | `ui/src/types/index.ts` |
| Main labeling UI | `ui/src/components/DocumentReview.tsx` |
| Auth context | `ui/src/context/AuthContext.tsx` |

### Environment Variables

```bash
AZURE_DI_ENDPOINT=https://...       # Azure Document Intelligence
AZURE_DI_API_KEY=...                # Azure DI API key
OPENAI_API_KEY=...                  # OpenAI API key
```

### Useful Commands

```bash
# Backend
.\scripts\dev-restart.ps1           # Start clean backend
.\scripts\kill-uvicorn.ps1          # Kill stale processes
.\scripts\test.ps1                  # Run tests

# Frontend
cd ui && npm run dev                # Start frontend
cd ui && npm test                   # Run frontend tests

# Pipeline
python -m context_builder.cli --help
```

---

*Generated for ContextBuilder codebase onboarding. Last updated: 2026-01.*
