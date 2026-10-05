# Development log

## October 4, 2026

- Implemented contact-scoped human-reviewed fact/preference memory with immutable revisions, required source/message citations, pinned source fingerprints, reasons, and timezone-normalized effective times.
- Added corrections, explicit withdrawal, history inspection, and a local CLI. Revisions use serialized transactions and expected revision numbers so a stale editor cannot overwrite another edit. Context observes exclusive cutoffs, rejects wrong-contact/future support, and suppresses memory if any cited message is removed or changes. Withdrawal also excludes historical context; the audit retains earlier text and is not a privacy-erasure mechanism.
- Added an in-memory synthetic walkthrough to CI; the fixed retrieval benchmark is unchanged. No private messages, exports, databases, or credentials were used or committed.
- Verification: 27 unit tests passed, including persistence across connections, stale editors, failed-edit rollback, citation invalidation, correction cutoffs, withdrawal, and CLI creation/history/listing. All 20 fixed retrieval cases passed with zero boundary violations; the synthetic walkthrough created, corrected, and withdrew one cited item successfully.
- Interview explanation: "I made personal memory editable and auditable: every fact cites the original conversation, corrections preserve history, and withdrawn or stale-source facts cannot be reused in context."
- Still pending: permanent privacy erasure, automatic extraction, embedding retrieval, draft generation, review UI, and real-user reply-quality evaluation. Human-reviewed citations do not automatically establish entailment.

## October 3, 2026

- Added a fixed synthetic benchmark: 31 invented messages, seven conversation partitions, six development cases, and 14 held-out retrieval cases. Cases retain explicit owner/contact/cutoff, source labels, outbound examples, and forbidden future/cross-contact records.
- Added an in-memory evaluation runner with per-case recall/precision, missing/unexpected source IDs, owner-example coverage, boundary checks, and a manifest/fixture fingerprint. The CLI fails on regressions and is now part of CI.
- Added cold-start and incoming-only situations. Manifest checks reject overlapping conversation partitions, future expected context, unknown provenance, and another person's writing labeled as owner style.
- Verification: 18 unit tests passed; all 20 benchmark cases passed with all labeled context retrieved and zero boundary violations. A deliberately broken retriever is detected by the evaluator. No messages or databases are exported by the runner.
- Interview explanation: "I built a fixed, provenance-labeled benchmark before adding generation, so I can detect missing context and prove that future messages or another contact's conversation do not leak into a reply."
- Still pending: source-aware editable memory, embedding retrieval, draft generation, review UI, and real-user reply-quality evaluation. The current small synthetic score is a regression check, not a generalization result.

## October 2, 2026

- Added `import --preview` with valid/invalid/skipped/duplicate counts and record-level error summaries for all three supported export formats.
- Existing stores are opened read-only during planning; preview creates no database or directory. Normal imports reject the entire file if validation fails.
- Duplicate planning matches provider-ID and normalized-content constraints both within an export and against the existing store. Error reports omit message bodies and invalid field values.
- Verification: 13 tests passed, including byte-for-byte unchanged existing stores, absent-database preview, rejected partial imports, multiple malformed records, MBOX/CSV diagnostics, and successful apply/reimport. The synthetic CLI preview reported five valid candidates and zero inserted records.
- Interview explanation: "I separated import inspection from persistence, so a user can review malformed records and duplicates before anything is stored."
- Still pending: the fixed evaluation benchmark, memory editing, embeddings, draft generation, and review UI. Candidate messages are currently materialized in memory during import planning.

## September 29, 2026

- Started the project with normalized local JSONL, MBOX, and outbound Discord CSV importers.
- Implemented a SQLite provenance store and a transparent lexical retrieval baseline with contact and time boundaries.
- Added synthetic examples and tests for future/cross-contact leakage, quote deduplication, persistence, import rollback, and export parsing.
- Reply generation, embeddings, memory editing, and a UI remain future work.
- Verification: seven unit tests passed; the CLI demo imported five synthetic messages, reimported zero duplicates, and excluded other-contact and future messages. Added GitHub Actions checks for Python 3.11 and 3.13.
