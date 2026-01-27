# Handoff: Image Highlighting & Vision Enrichment

**Date:** 2026-01-26
**Status:** In Progress
**Priority:** High

## Problem Statement

Evidence highlighting in the Claims Explorer UI was not working for:
1. **NSA documents** - Extracted fields had no provenance data (no clickable evidence links)
2. **Image documents** - No word-level coordinates available for bounding box highlighting

## Root Cause Analysis

### Issue 1: Missing Provenance in Extractions (FIXED)

**Cause:** LLM extraction was returning values but not `text_quote` for most fields (only 12.5% had provenance).

**Solution Implemented:**
- Enhanced `evidence_resolver.py` with `backfill_evidence_from_values()` function
- Searches Azure DI tables for exact cell matches (most precise)
- Falls back to page text search with Swiss/German number normalization
- Run via CLI: `python -m context_builder.cli backfill-evidence`

**Result:** NSA extractions improved from 12.5% to 80%+ fields with provenance.

**Files Modified:**
- `src/context_builder/extraction/evidence_resolver.py` - Added backfill logic
- `src/context_builder/extraction/backfill.py` - Updated to pass Azure DI data

### Issue 2: Images Using OpenAI Vision (NO Coordinates) (PARTIALLY FIXED)

**Cause:** Images were routed through OpenAI Vision which returns `vision.json` with text content but NO word-level polygon coordinates. Only PDFs had `azure_di.json` with coordinates.

**Solution Implemented (Phase 1):**
- Changed `ingestion.py` to route images through Azure DI (same as PDFs)
- Images now get `azure_di.json` with word-level coordinates for highlighting

**Files Modified:**
- `src/context_builder/pipeline/stages/ingestion.py` - Route images to Azure DI

### Issue 3: Classification May Fail Without Vision Context (TO BE IMPLEMENTED)

**Risk:** Azure DI OCR on images like dashboard photos may return minimal text (e.g., just "74359"), causing classification to fail or return "unknown". Vision provides semantic understanding that helps classify such images correctly.

**Agreed Solution: Option C - Always Run Both for Images**

For image documents, run BOTH:
1. **Azure DI** - For OCR text AND word-level coordinates (highlighting)
2. **OpenAI Vision** - For semantic understanding (classification + extraction context)

## Implementation Plan for Option C

### Architecture

```
Image Document Flow:

┌─────────────────────────────────────────────┐
│            Ingestion Stage                   │
│                                              │
│   ┌─────────────┐    ┌─────────────┐        │
│   │  Azure DI   │    │   Vision    │        │
│   │ (parallel)  │    │ (parallel)  │        │
│   └──────┬──────┘    └──────┬──────┘        │
│          │                  │               │
│          ▼                  ▼               │
│   azure_di.json       vision.json           │
│   (coordinates)       (semantic text)       │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│          Classification Stage                │
│                                              │
│   Use COMBINED text from:                   │
│   - Azure DI content (OCR)                  │
│   - Vision text_content (semantic)          │
│                                              │
│   Classifier gets best of both worlds       │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│          Extraction Stage                    │
│                                              │
│   - Uses Azure DI text for extraction       │
│   - Azure DI coordinates for provenance     │
│   - Vision data available if extractor      │
│     needs semantic context                  │
└─────────────────────────────────────────────┘
```

### Changes Required

#### 1. Update `ingestion.py` - Run Both Providers for Images

```python
# In ingest_document() for images:
elif doc.source_type == "image":
    # Run Azure DI for coordinates
    azure_result = _ingest_with_provider(doc, doc_paths, writer, factory, "azure-di")

    # Also run Vision for semantic understanding
    try:
        vision_result = _ingest_with_vision(doc, doc_paths, writer, factory)
    except Exception as e:
        logger.warning(f"Vision enrichment failed: {e}")
        vision_result = None

    # Return Azure DI result (has coordinates) but store both
    return IngestionResult(
        text_content=azure_result.text_content,
        provider_name="azure-di",
        azure_di_data=azure_result.azure_di_data,
        vision_data=vision_result,  # NEW: Also include vision data
    )
```

#### 2. Update `IngestionResult` in `context.py`

```python
@dataclass
class IngestionResult:
    text_content: str
    provider_name: str
    azure_di_data: Optional[Dict[str, Any]] = None
    vision_data: Optional[Dict[str, Any]] = None  # NEW
```

#### 3. Update Classification to Use Combined Text

In `classification.py`, when classifying images, combine text from both sources:

```python
if context.doc.source_type == "image" and context.vision_data:
    # Combine Azure DI OCR with Vision semantic text
    vision_text = context.vision_data.get("pages", [{}])[0].get("text_content", "")
    combined_text = f"{context.text_content}\n\n--- Vision Analysis ---\n{vision_text}"
    classification = context.classifier.classify(combined_text, context.doc.original_filename)
else:
    # Use standard classification
    classification = context.classifier.classify(context.text_content, ...)
```

#### 4. Store Vision Data in Context

Update `IngestionStage.run()` to store vision data:

```python
if context.doc.source_type == "image":
    ingestion_result = ingest_document(...)
    context.text_content = ingestion_result.text_content
    azure_di_data = ingestion_result.azure_di_data
    context.vision_data = ingestion_result.vision_data  # NEW
```

#### 5. Delete VisionEnrichmentStage (No Longer Needed)

Since Vision runs during ingestion for all images, the separate VisionEnrichmentStage is no longer needed. Delete:
- `src/context_builder/pipeline/stages/vision_enrichment.py`

Or repurpose it for PDF documents that might benefit from Vision (rare case).

### Files to Modify

| File | Change |
|------|--------|
| `src/context_builder/pipeline/stages/context.py` | Add `vision_data` to `IngestionResult` |
| `src/context_builder/pipeline/stages/ingestion.py` | Run both Azure DI + Vision for images |
| `src/context_builder/pipeline/stages/classification.py` | Use combined text for image classification |
| `src/context_builder/pipeline/stages/vision_enrichment.py` | Delete or repurpose |

### Testing Plan

1. **Re-ingest NSA images:**
   ```bash
   python -m context_builder.cli pipeline workspaces/nsa/input --stages ingest
   ```

2. **Verify both files created for images:**
   ```bash
   ls workspaces/nsa/claims/*/docs/*/text/raw/
   # Should see both azure_di.json AND vision.json for images
   ```

3. **Run full pipeline and check classification:**
   ```bash
   python -m context_builder.cli pipeline workspaces/nsa/input
   ```

4. **Check UI highlighting:**
   - Open http://localhost:5173/claims/explorer
   - Select a claim with image documents (e.g., KM.jpg)
   - Verify extracted fields have clickable evidence links
   - Click evidence link and verify bounding box highlighting on image

### Rollback Plan

If Option C causes issues (cost, latency), revert to Option B (Vision as fallback):
- Only run Vision when classification returns "unknown" or confidence < 0.7
- Implementation exists in `vision_enrichment.py` (currently post-classification)

## Current State Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Evidence backfill from values | ✅ Done | `backfill-evidence` CLI works |
| Azure DI for images | ✅ Done | Images route to Azure DI |
| VisionEnrichmentStage | ✅ Created | Post-classification, for specific doc types |
| Option C (both for images) | ❌ TODO | Need to run Vision during ingestion |
| Combined text classification | ❌ TODO | Use both texts for classification |
| UI highlighting for images | ❌ Blocked | Needs re-ingestion with Azure DI |

## Commands Reference

```bash
# Backfill evidence for existing extractions
python -m context_builder.cli backfill-evidence

# Re-run pipeline on NSA workspace
python -m context_builder.cli pipeline workspaces/nsa/input

# Re-run just ingestion stage
python -m context_builder.cli pipeline workspaces/nsa/input --stages ingest

# Check active workspace
python -c "from context_builder.storage.workspace_paths import get_active_workspace; print(get_active_workspace())"
```

## Key Files

- `src/context_builder/extraction/evidence_resolver.py` - Backfill logic
- `src/context_builder/extraction/backfill.py` - Workspace backfill CLI
- `src/context_builder/pipeline/stages/ingestion.py` - Document ingestion
- `src/context_builder/pipeline/stages/classification.py` - Classification
- `src/context_builder/pipeline/stages/context.py` - Pipeline context/dataclasses
- `src/context_builder/pipeline/stages/vision_enrichment.py` - Vision stage (may be deleted)
- `ui/src/components/DocumentViewer.tsx` - UI highlighting orchestration
- `ui/src/lib/bboxUtils.ts` - Bounding box computation
