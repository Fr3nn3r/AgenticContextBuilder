### Handlers module size review (intake/processors/content_support/handlers.py)

#### Short answer
A ~1,000-line `handlers.py` is too large for long-term maintainability. It likely violates SRP/KISS and will slow reviews, testing, and change velocity. Break it down by handler and shared utilities.

#### What “good” looks like
- High cohesion per file (one purpose), low coupling across files
- Functions ≤50–80 lines; files typically ≤200–400 lines
- Cross-cutting concerns (OpenAI calls, JSON cleaning, PDF rendering/OCR) live in small reusable modules
- Lazy imports for heavy deps (e.g., `pdfium`, `PIL`, `pandas`) within specific modules

#### Recommended structure (concrete)
```
intake/processors/content_support/handlers/
  __init__.py           # exports
  base.py               # handler interface/contract
  text_handler.py
  image_handler.py
  sheet_handler.py
  document_handler.py
  pdf/
    __init__.py
    common.py          # rendering, page iteration, JSON cleaning utilities
    vision.py          # Vision API based extraction
    ocr.py             # OCR/unstructured flows
ai_client.py            # OpenAI wrapper with retry/backoff
utils.py                # clean_json_response, file size checks, system-file rules
```
Keep `PromptManager` as-is and inject it (plus `AiClient`) into handlers to respect DIP.

#### Immediate wins from splitting
- Easier unit tests per handler/util
- Cleaner diffs/reviews and faster onboarding
- Fewer merge conflicts; lower cognitive load
- Clearer boundaries for performance-sensitive imports and execution

#### When it’s acceptable to keep as-is (briefly)
- Short-lived spike or ongoing refactor with near-term split planned
- If most code is temporary diagnostic code to be pruned imminently

#### Recommendation
Given you’re past an initial refactor, now is the right time to split. Aim for cohesive files per handler and extract PDF-specific flows into submodules. This aligns with SRP/KISS from `CLAUDE.md`, improves testability, and reduces maintenance cost.


