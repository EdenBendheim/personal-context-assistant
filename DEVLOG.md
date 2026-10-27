# Development log

## October 26, 2026

- Import preview now distinguishes conflicting provider IDs from genuine
  duplicates, rejects an ambiguous batch without writes, and reserves content
  aliases within the file. Apply checks IDs again under a writer transaction
  and rolls back if another import changed the store after preview. Errors
  omit message values. Nine import-preview tests and seven context tests pass,
  including within-file aliases, conflicting existing records, an intervening
  writer, CLI failure reporting and preservation of pending user writes.

- Added bounded cursor pages and topic/revision labels for saved reviews, with
  a browser control that preserves unsaved wording and the current selection.
  Store tests reached all 105 timestamp-tied reviews while another review arrived;
  wrong-scope and removed cursors fail clearly. HTTP limits/auth tests pass.
  A real browser loaded all 29 synthetic reviews, opened the oldest, preserved
  unsaved text, and refreshed stale-rating counts after memory withdrawal;
  no console errors. No private conversations or actual inference used.

- Fixed current feedback summaries retaining usable ratings after supporting
  sources changed. Summary and per-draft review now use the same context check;
  stale counts explain exclusions while feedback history remains intact. The
  browser refreshes metrics after memory updates. Regression checks cover
  deleted/edited messages, withdrawn memory, a still-current generic draft and
  owner isolation, plus the HTTP path. No real-model quality claim.

## October 23, 2026 — daily run completed October 24

- Added authenticated owner-fixed privacy preview/apply routes and a workspace
  panel with affected-record counts, typed identifier gating and final explicit
  confirmation. Every write/contact switch clears the preview; server checks
  also refuse stale state. Contacts with only saved copies stay selectable.
  Three new HTTP tests pass, including orphaned raw sources and shared-copy
  refusal; existing owner/auth and review tests remain green.
- Final local checks: all 101 tests pass, all 20 fixed lexical retrieval cases
  retain recall/precision 1.0 with zero boundary violations, all 13 scripted
  generation cases pass, memory/draft demos and JS syntax/whitespace checks pass.
  Real in-app browser check verified counts, typed-confirmation gating and
  contact-switch invalidation. No real model/service, private data or paid
  compute was used. No personal database or source export was removed.
- Limitations: removal covers live records in the selected database scope;
  external exports/backups, another open browser's display, uncited manual
  copies, provider logs and physical storage remnants are not erased. Reimport
  can restore data. Other-scope cited copies block removal. Real reply quality,
  local model verification and export tracking remain pending.
- Interview explanation: “I traced contact data through messages, memory and
  saved draft histories, made removal previewable and transactional, rejected
  stale or shared-scope plans, and verified that other contacts stay intact.”

- Added explicit SQLite index rebuild with before/after integrity checks and
  exact application-record fingerprint equality under a writer transaction.
  Three synthetic checks pass for preserved retrieval/memory/reviews, rebuild
  after removal, rollback on unexpected changes, pending-write refusal and
  missing-file CLI behavior. This rebuilds SQLite indexes, not an embedding
  index or a physical-erasure mechanism.

- Added a preview-first privacy CLI requiring the exact plan hash and a
  separate explicit deletion flag. Existing-only SQLite connections avoid
  recreating a missing file or migrating its schema. Three CLI tests pass for
  preview/apply, stale-plan refusal, missing stores and untouched source exports.
  No external file is unlinked and no personal database was used.

- Added explicitly confirmed removal of the reviewed contact scope under a
  SQLite writer transaction. The exact snapshot/plan is rechecked before
  deleting child records, and untouched rows must remain identical. Secure
  delete is enabled for the operation, with its prior setting restored. Seven
  privacy tests pass, including concurrent edits, retained other-scope copies,
  full rollback after injected failure and preservation of another contact.
  This removes current live database copies, not exports/backups or physical
  storage remnants. Only synthetic stores were used.

- Added a read-only contact-removal preview covering raw messages, memory
  revisions/citations, original draft packets, wording edits and feedback.
  Counts and a snapshot-bound plan hash omit message text. Other-scope retained
  source copies block removal; unknown/incomplete schemas and pending writes
  fail closed. Three synthetic tests pass, including unchanged database bytes.
  Applying removal remains pending; external exports/physical erasure are outside
  the preview contract. No real messages were inspected or removed.

## October 21, 2026

- Final local verification: all 85 tests passed. All 20 unchanged lexical
  retrieval cases retained recall/precision 1.0 with zero boundary violations
  and fingerprint d43ffd7edd646635a2357378d75a06fc75d7e45ef5665363a3f66f0997c4e77c.
  All 13 scripted drafting cases and both memory/draft walkthroughs passed.
  No real model was available; learned embedding quality remains unverified.
- Interview explanation: "I added optional local embedding search while keeping
  lexical retrieval as a baseline. History is filtered before encoding and
  checked afterward. The paired evaluator exposes worse results as well as
  improvements; synthetic contract tests don't prove model quality."

- Added paired fixed-case lexical/embedding evaluation with fingerprinted cases,
  configuration snapshots, per-case failures, boundary counts and visible metric
  deltas. Three tests exercise synonym routing, worse embedding precision,
  configuration changes, fixed-manifest CLI failures and local-only confirmation.
  All vectors are handwritten fixtures, not trained-model results. No model
  quality or reply-quality improvement is claimed.

- Added a separate embedding-search CLI with explicit model/local-only options,
  provider provenance and a read-only existing-store mode. Three synthetic HTTP
  integration tests cover a full command, unchanged SQLite bytes/write refusal,
  missing-store and unconfirmed-service refusal, and errors without fallback.
  Default search, drafting and browser retrieval remain lexical.

- Added the opt-in loopback Ollama embedding adapter. Four synthetic HTTP tests
  cover the batched API, disabled truncation, proxy bypass, configuration/input
  refusal, redirects/errors, malformed vectors, response bounds and redacted
  timeouts. No installed model, model download or paid service was used.

- Added opt-in cosine retrieval scoped before encoding to the selected contact
  and exclusive cutoff, with retained provenance/outbound style separation and
  post-encoding source-change checks. Three synthetic checks cover synonym
  routing, no future/cross-contact provider inputs, stable ties, cold starts,
  candidate bounds and source mutation. No learned encoder or quality result.

- Added a bounded embedding-provider contract with strict response counts,
  finite/nonzero vectors, consistent dimensions, normalization and cosine scores.
  Two synthetic checks cover scale-invariant similarity, input isolation,
  malformed responses and refusal before provider calls. No model was installed
  or invoked; no semantic quality claim.

## October 17, 2026

- Final local verification: all 70 tests passed; all 20 unchanged retrieval
  cases retained recall/precision 1.0 with zero boundary violations, fingerprint
  d43ffd7edd646635a2357378d75a06fc75d7e45ef5665363a3f66f0997c4e77c.
  All 13 scripted drafting cases passed; memory/draft walkthroughs and JS
  syntax/whitespace checks passed. Real LLM inference remains unverified.

- Added a separately fingerprinted 13-case scripted drafting regression suite
  and CI gate. Three tests verify cases, detect a broken human-review flag and
  reject invalid/duplicate manifests. All 13 cases pass; two deliberately false
  wordings still require human review, exposing the lack of automatic semantic
  entailment. Fixed retrieval benchmark is unchanged. No model binary/service
  or confirmed cloud-disabled setup was available; actual inference and reply
  quality remain unmeasured. No downloads, paid APIs or private messages used.
- Interview explanation: "I added a local generative drafting path with source
  inspection and revision-bound human review, then tested failures separately
  from model quality. Genuine citations do not automatically make a paraphrase
  true, so the app records that review explicitly."


- Added browser generation-mode status, segmented wording/quote inspection,
  requested-configuration details and an explicit support selector. A real
  in-app browser check with a synthetic provider verified usable stays disabled
  until checked, feedback persists, and saving edited wording requires a new
  support assessment. HTML-shaped fixture text produced zero image elements
  and no console errors. Screenshot is local/ignored under runs/. JS syntax
  and three generation-entrypoint tests passed. No real LLM quality measured.

- Wired explicit local-model options into the draft CLI and review server,
  preserving default extractive behavior. Three entrypoint tests cover fixed
  server configuration, no request-selected endpoint, human-support feedback,
  unsaved abstentions and redacted inference outages without fallback success.
  The authenticated config endpoint reports mode/settings and no sending.

- Persisted generated packets/settings and revision-bound human support ratings.
  Usable generated drafts require an explicit supported assessment; edits need
  re-rating. Four tests cover migration, abstention/failure rollback, exact
  revision checks and another connection writing during inference without a
  held writer lock. Concurrent source changes cannot become a saved review.

- Added an opt-in loopback Ollama adapter using the official structured-chat
  contract. Four real synthetic HTTP tests cover bounded requests/provenance,
  no-proxy/no-redirect behavior, invalid/incomplete/tool responses, timeout
  redaction and preflight bounds. No real LLM, download or paid API was used.
  Enabling requires an explicitly confirmed cloud-disabled local daemon.

- Added a versioned structured drafting prompt/schema and strict JSON decoder.
  Two tests verify instruction/data separation, owner-example provenance,
  deterministic prompt fingerprints, length bounds and malformed/duplicate-key
  rejection. No model quality or prompt-injection resistance is claimed.

- Added a separate generative proposal contract with segmented wording, literal
  evidence quotes, explicit abstention, bounded output and source-change checks.
  Four synthetic tests cover unsupported/style-only citations, provider
  mutation, cold starts and source-linked false paraphrases remaining unapproved.
  These checks establish provenance, not semantic entailment or reply quality.

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
