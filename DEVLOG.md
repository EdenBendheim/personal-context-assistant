# Development log

## October 6, 2026

- Added browser and owner-scoped API memory creation, correction, withdrawal, and source/history inspection. Changed/missing citations are flagged; a source moved to another contact is never displayed. The panel reports the actual cutoff-eligible revision, and current-time edits require a rebuilt draft to enter its context. Lists are capped at 100 items; history pagination and permanent erasure remain pending.
- Final verification: all 50 unit/HTTP tests passed; the fixed 20-case retrieval benchmark retained recall/precision 1.0 and zero boundary violations (unchanged fingerprint). Chromium create/edit/withdraw succeeded; withdrawal flagged the affected draft stale and disabled a usable rating. No browser console errors; a 390px mobile viewport had exactly 390px content width and zero injected images. The wheel includes all local UI assets.
- Today's random selection was this repository, with a target of five useful commits. Work remains an extractive local baseline; language-model drafting, embedding comparisons, held-out reply quality, and permanent privacy erasure are pending.
- Interview explanation: "I built a local review application where drafts retain their evidence, edits and feedback are tied to exact revisions, and users can correct or withdraw cited memory without silently reusing stale context."

- Added a responsive local browser review screen with contact/topic/cutoff selection, inspectable evidence and writing examples, editable drafts, saved-review history, and revision-bound feedback. Unsaved wording disables ratings and prompts before discarding; the page never sends a message. Packaged HTML/JS/CSS as local assets.
- Verification for this step: all 46 tests passed. In a real Chromium browser, created a review, edited/saved revision 2, recorded usable/useful feedback, and reloaded to see persistent counts. An HTML-shaped synthetic message rendered literally with zero injected images and an unchanged page title.

- Added a dependency-free loopback HTTP API for contact selection, draft creation/reopening, edits, feedback, and summaries. It fixes the owner at launch and rejects invalid tokens, Host/Origin headers, malformed/oversized bodies, and conflicting edits. It omits traffic logs and prevents missing-database recreation.
- Verification for this step: all 45 tests passed, including four real HTTP integration tests covering persisted edit/feedback round trips, owner isolation, source deletion, bad field types, and request boundaries.

- Added revision-bound usable/needs-work/rejected feedback, separate retrieval/style ratings, and contact-scoped summaries. Repeated assessments count once per current revision; edited drafts require re-rating. Stale-context drafts cannot be marked usable. Word overlap is explicitly an order-insensitive editing diagnostic.
- Verification for this step: six review tests passed, including invalid ratings, withdrawn sources, stale revisions, repeat ratings, edited-rating exclusion, and empty contact summaries.

- Added persistent review packets and immutable draft edits with owner-scoped access, contact filtering, optimistic revision checks, and current-context fingerprints. Cold starts are not saved as empty reviews; unchanged saves do not create revisions.
- Verification for this step: four new tests passed, including reconnect persistence, two-connection stale edits, owner isolation, changed sources, and pending-transaction rollback boundaries.
- Interview explanation: "I made draft reviews resumable while preserving the original evidence and every wording revision, so an outdated browser cannot silently overwrite another edit."

## October 5, 2026

- Added generic/context/personalized draft review packets combining eligible past messages, cited memory, and outbound examples. Added a local extractive quote-provider interface, bounded literal-quote validation, provenance-bearing citations, a template reply, and explicit needs-history/needs-review outcomes.
- Providers receive an isolated copy of the packet. The engine checks stored source/contact/time boundaries and rebuilds the packet before returning: edits or revocations during provider work invalidate it. Unknown, fabricated, style-only, duplicate, or oversized quote proposals are rejected. Style examples alone cannot supply factual context.
- Added a local CLI and an in-memory invented-message walkthrough to CI. Drafts/runs are ignored to keep future real review output private. There is no model/API call or message sending; the existing fixed retrieval benchmark is unchanged.
- Verification: 35 unit tests passed; all 20 retrieval benchmark cases still passed with zero boundary violations. The synthetic walkthrough produced distinct generic/context/personalized packets with 0/2/3 citations, and an unknown contact returned an empty needs-history result. Tests also cover provider mutation isolation, source edits/memory revocation during drafting, and broken retrieval boundaries.
- Interview explanation: "I connected retrieval and editable memory to a draft review pipeline, so users can inspect every quote and the system refuses stale or unsupported context before showing the draft."
- Still pending: language-model drafting, semantic entailment checks, style imitation/quality evaluation, embedding retrieval, review UI, and permanent privacy erasure. Literal quote provenance is not factual truth or demonstrated reply quality.

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
