Compliance Storage Backends - Implementation Plan

Context
- Goal: compliance subsystem supports alternate storage backends (S3, DB, encrypted local) soon.
- Keep modules split with a shared common base (interfaces + shared record factories).
- Track nice-to-have and out-of-scope items explicitly.

Scope Assumptions
- Decision ledger and LLM audit logging remain append-only with integrity checks.
- API and pipeline components should depend on small interfaces, not concrete storage.
- No network access in this task; plan only.

Plan (must-have)
1) Define storage interfaces and data models (common base)
   - Add protocols/interfaces for:
     - DecisionAppender (append-only)
     - DecisionReader (query by filters)
     - DecisionVerifier (integrity checks)
     - LLMCallSink (append-only)
     - LLMCallReader (query by call_id/decision_id)
   - Add shared DTOs for IO boundaries (DecisionRecord, LLMCallRecord remain as-is).
   - Centralize DecisionRecord creation in a DecisionRecordFactory (common base).
   - Target files: src/context_builder/services/, src/context_builder/schemas/

2) Refactor current implementations to implement interfaces (local filesystem)
   - Split DecisionLedger into:
     - FileDecisionAppender
     - FileDecisionReader
     - FileDecisionVerifier
     - Optional DecisionLedgerFacade to preserve current API
   - Split LLMAuditService into:
     - FileLLMCallSink
     - FileLLMCallReader
   - Ensure existing behavior is preserved and fully covered by unit tests.

3) Introduce configuration and composition root wiring
   - Add a ComplianceStorageConfig (backend type + connection params).
   - Provide a factory: ComplianceStorageFactory
     - returns interface implementations based on config
   - Wire in CLI/API entry points to construct and inject dependencies.
   - Do not instantiate storage inside services (remove service locator usage).

4) Add backend implementations (minimal viable)
   - Encrypted local backend
     - Use envelope encryption or file-level encryption (implementation decision TBD).
     - Ensure append-only semantics preserved (hash chain over plaintext vs ciphertext: decide and document).
   - S3 backend
     - Append-only storage with object versioning or per-record objects + manifest.
     - Integrity verification mechanism (hash chain stored in object metadata or a manifest).
   - DB backend
     - Use append-only table with chain hash column and strict insert-only policy.

5) Update tests and fixtures
   - Add shared contract tests for the interfaces (append/query/verify behavior).
   - Reuse the same test suite for file/S3/DB/encrypted local via fixtures.
   - Add regression tests for current ledger + audit files to ensure no breaking changes.

6) Documentation updates
   - Update README / docs with backend configuration examples.
   - Document integrity semantics and threat model for each backend.
   - Describe storage layout and migration steps from file-only.

Nice-to-have
- Async/batched writes for high-throughput audit logs.
- Streaming query API for large ledgers.
- Key rotation tooling for encrypted backend.
- Optional compression for JSONL records.
- Optional redaction hooks before persistence (for decision log PII minimization).

Out of scope (explicit)
- Full data migration tooling from file-ledger to DB/S3.
- Multi-region replication strategy and SLAs.
- UI changes for selecting backend at runtime.
- Real-time monitoring/alerting integration (e.g., SIEM).

Proposed sequencing
1) Interfaces + factory + file backend refactor
2) Encrypted local backend
3) DB backend
4) S3 backend
5) Contract test suite across all backends

Exit criteria
- All compliance services use injected interfaces, no hardcoded storage dirs.
- File backend passes contract tests.
- At least one alternate backend (encrypted local) passes contract tests.
