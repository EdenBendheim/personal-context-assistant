# Development log

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
