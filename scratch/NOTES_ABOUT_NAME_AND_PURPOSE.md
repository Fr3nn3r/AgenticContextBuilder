What you’re building, in industry terms, is best described as a:

**Document Intelligence extraction pipeline + benchmarking/labeling workbench**
(or shorter: **Document Extraction Benchmarking Workbench**).

More specifically, it combines:

* **IDP / Document AI** (ingest → classify → extract with provenance)
* **Human-in-the-loop labeling** (ground truth capture)
* **Evaluation/benchmarking** (run-based KPIs vs truth across versions)
* (and the beginnings of) **model/pipeline ops** for document extraction (run manifests, metrics snapshots)

That’s a real category. Vendors call adjacent things:

* “IDP platform”
* “Document AI” / “Document intelligence”
* “Extraction QA” / “Calibration”
* “Evaluation workbench”

### Is “AgenticContextBuilder” a good name?

For internal/dev usage: sure. For an industry-facing product name: I’d avoid it.

Why:

* **“Agentic”** is buzzword-heavy and currently overloaded (and triggers skepticism in regulated buyers).
* It also implies autonomous actions, whereas your core value is **traceable extraction + benchmarking**.

A better name should communicate:

* documents → structured context
* evidence/traceability
* benchmarking / quality

Better options (same vibe, more credible):

* **ContextBuilder** (you already moved here—good)
* **ContextBuilder for Document AI**
* **ContextBuilder Bench**
* **EvidenceContext**
* **TraceContext**
* **DocContext**
* **ContextBuilder IDP**

If you want one crisp positioning line to go with the name:

> **ContextBuilder — traceable document extraction with built-in benchmarking.**

If you tell me your target buyer for this tool (internal Zurich teams vs selling to insurers vs general SaaS), I can recommend the strongest naming/positioning combo.
