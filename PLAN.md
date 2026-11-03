# Build plan

Started September 29, 2026. Dates below are targets, not completed claims.

## Milestone 1 — ingestion and evaluation data

- [x] Common message schema, local export importers, provenance, and quote cleanup.
- [x] Atomic SQLite persistence and deduplication.
- [x] Contact-specific lexical retrieval and outbound style examples with timestamp cutoffs.
- [x] Keep lexical search/style CLI lookups read-only and refuse missing stores without creating files.
- [x] Add importer error summaries and an explicit preview before committing an import.
- [x] Distinguish conflicting provider IDs from true duplicates and recheck conflicts atomically at apply time.
- [x] Add conversation-level development/evaluation manifests and a fixed synthetic reply-context retrieval benchmark.
- [x] Define contact-scoped, source-aware memory with immutable correction/withdrawal history.
- [x] Add explicit memory editing, provenance invalidation, and stale-editor protection.

## Milestone 2 — drafting and retrieval comparisons

- [x] Add an optional embedding search backend/CLI behind the same retrieval contract; retain lexical baseline.
- [x] Add a paired fixed-case retrieval comparison with source boundaries, provider settings and visible regressions.
- [x] Verify an installed cloud-disabled embedding model, freeze settings on development cases and report held-out synthetic retrieval results.
- [x] Decide whether measured embedding results justify integration into drafting and the review UI: retain lexical defaults after a tie on the small established benchmark.
- [x] Audit required reply sources independently of generation, with exact fixture-bound annotations.
- [x] Add opt-in bounded same-thread followups to draft/evaluation CLIs and measure a fixed comparison without changing stored reviews.
- [x] Add an extractive quote-provider contract and an inspectable draft packet with citations.
- [x] Separate generic, context-only, and personalized context configurations.
- [x] Reject unavailable/nonliteral quotes and stale context; abstain when factual history is insufficient.
- [x] Add an opt-in local model adapter using retrieved citations and recipient examples, with strict response validation, abstention and revision-bound human support review.
- [x] Verify a real installed, cloud-disabled local model on synthetic reply cases, with model/file receipts and failures retained.
- [ ] Add semantic support checks for generated factual prose and evaluate style/reply quality.

## Milestone 3 — useful application

- [x] Add a loopback HTTP review API with a fixed owner, per-launch authorization, bounded requests, and integration checks.
- [x] Persist original draft packets and immutable wording revisions with owner isolation and stale-editor checks.
- [x] Browse all saved reviews with bounded, owner/contact-scoped cursor pages and topic/revision labels.
- [x] Browse memory and revision history with bounded, source-aware pages that preserve unsaved wording.
- [x] Browse draft wording and revision-bound feedback with separate bounded pages, preserving unsaved editors.

- [x] Build contact selection, source inspection, draft editing/reopening, and feedback in a local review interface.
- [x] Add cited-memory creation/correction/withdrawal to that browser interface.
- [x] Add snapshot-bound contact removal including saved packets and revision copies, with CLI/API/UI confirmation.
- [x] Rebuild SQLite indexes with integrity and unchanged-record checks.
- [ ] Track original export files and offer explicit external-export deletion; backups/manual copies remain outside database removal.
- [x] Record useful/incorrect retrievals and changed wording without sending messages automatically.
- [x] Exclude changed-source ratings from current feedback totals and refresh browser counts after memory changes.
- [x] Publish synthetic demo commands, a browser walkthrough, and an architecture explanation.

## Milestone 4 — measured results

- [ ] Approximately 50 held-out reply situations, subject to suitable data availability.
- [ ] Blind style/preference comparison with generic drafting, factual support, edits, latency/cost.
- [x] Report initial real-model failure examples and uncertainty, not only successful screenshots; expand with the larger reply study.
- [ ] Consider a style adapter only if retrieval/prompting plateau and the dataset supports a clean evaluation.

## Next session

November 1: real cloud-disabled inference is unblocked. Exact runtime/model
receipts and all local model blobs verify; pinned adapters detect metadata drift.
Nomic at a development-selected cosine threshold of 0.6 ties lexical retrieval
on all 14 established synthetic evaluation cases. Default drafting/UI retrieval
stays lexical; no embedding improvement is claimed.

Qwen2.5 1.5B runs through the CLI and browser. Development exposed mixed
reply/abstention outputs; v3 constrains those shapes without weakening validation.
Frozen evaluation produced seven abstentions and three drafts requiring review,
plus two no-history skips across 12 mode attempts. The drafts are unhelpful or
too vague; development also exposed an unsupported availability claim and
repetition. This is a working inference path, not useful owner-style generation.
See [the full study](experiments/LOCAL-INFERENCE-2026-11-01.md).

November 2: source-coverage diagnostics now expose the old equipment omission;
window-1 thread expansion recovers it. A separate twelve-case stress set improves
required-source coverage from 0/6 to 4/6 evaluation contacts. Both controlled 7B
variants still abstain on all 16 evaluation model calls each. Source coverage is
not reply usefulness, and a larger model did not resolve this run's behavior.
See [the paired study](experiments/FOLLOWUP-EVIDENCE-2026-11-02.md).

Next retain abstention reasons and add explicit communication intent/current
message to the request rather than relying on a topic word. Keep compatibility
with saved packets, test development-only prompt changes, then freeze a new
evaluation version. Collect human factual/usefulness ratings before style claims
or fine-tuning. Missing lexical seeds, distant and separate-thread facts remain
outside the new neighbor adapter. UI and saved-review defaults stay lexical;
the CLI option is deliberate and source-traceable. Grow beyond the small authored
stress sets while preserving these failures and the human review gate.

History APIs/browser now page memories, corrections, saved reviews, wording and
feedback; a real browser reached 30 draft revisions/ratings without losing unsaved
fields. Legacy full-history APIs remain. Large-history embedding indexing,
external-export/backup tracking, automatic memory extraction and real-user
evaluation remain pending. No sending integration is planned.
