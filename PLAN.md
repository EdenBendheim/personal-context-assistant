# Build plan

Started September 29, 2026. Dates below are targets, not completed claims.

## Milestone 1 — ingestion and evaluation data

- [x] Common message schema, local export importers, provenance, and quote cleanup.
- [x] Atomic SQLite persistence and deduplication.
- [x] Contact-specific lexical retrieval and outbound style examples with timestamp cutoffs.
- [x] Add importer error summaries and an explicit preview before committing an import.
- [x] Add conversation-level development/evaluation manifests and a fixed synthetic reply-context retrieval benchmark.
- [x] Define contact-scoped, source-aware memory with immutable correction/withdrawal history.
- [x] Add explicit memory editing, provenance invalidation, and stale-editor protection.

## Milestone 2 — drafting and retrieval comparisons

- [x] Add an optional embedding search backend/CLI behind the same retrieval contract; retain lexical baseline.
- [x] Add a paired fixed-case retrieval comparison with source boundaries, provider settings and visible regressions.
- [ ] Verify an installed cloud-disabled embedding model, freeze settings on development cases and report held-out retrieval results.
- [ ] Decide whether measured embedding results justify integration into drafting and the review UI.
- [x] Add an extractive quote-provider contract and an inspectable draft packet with citations.
- [x] Separate generic, context-only, and personalized context configurations.
- [x] Reject unavailable/nonliteral quotes and stale context; abstain when factual history is insufficient.
- [x] Add an opt-in local model adapter using retrieved citations and recipient examples, with strict response validation, abstention and revision-bound human support review.
- [ ] Verify a real installed, cloud-disabled local model on synthetic reply cases (adapter has synthetic HTTP tests only).
- [ ] Add semantic support checks for generated factual prose and evaluate style/reply quality.

## Milestone 3 — useful application

- [x] Add a loopback HTTP review API with a fixed owner, per-launch authorization, bounded requests, and integration checks.
- [x] Persist original draft packets and immutable wording revisions with owner isolation and stale-editor checks.

- [x] Build contact selection, source inspection, draft editing/reopening, and feedback in a local review interface.
- [x] Add cited-memory creation/correction/withdrawal to that browser interface.
- [x] Add snapshot-bound contact removal including saved packets and revision copies, with CLI/API/UI confirmation.
- [x] Rebuild SQLite indexes with integrity and unchanged-record checks.
- [ ] Track original export files and offer explicit external-export deletion; backups/manual copies remain outside database removal.
- [x] Record useful/incorrect retrievals and changed wording without sending messages automatically.
- [x] Publish synthetic demo commands, a browser walkthrough, and an architecture explanation.

## Milestone 4 — measured results

- [ ] Approximately 50 held-out reply situations, subject to suitable data availability.
- [ ] Blind style/preference comparison with generic drafting, factual support, edits, latency/cost.
- [ ] Report failure examples and uncertainty, not only successful screenshots.
- [ ] Consider a style adapter only if retrieval/prompting plateau and the dataset supports a clean evaluation.

## Next session

The local generative path is implemented end to end: versioned prompts and JSON
schema, bounded loopback Ollama client, saved original segments/support/config,
explicit human support ratings, CLI/server opt-in and browser inspection. Default
remains extractive. Thirteen scripted contract cases are distinct from unchanged
retrieval evaluation; two intentionally false wordings remain for human review,
so semantic entailment is not automated or demonstrated.

No installed Ollama service/cloud-disabled setup was available on October 21.
Next: use an already installed local model with cloud disabled, record its exact
weights/runtime and run bounded synthetic inference. Build held-out reply
situations and blind comparisons before claiming style imitation or improved
reply quality. An opt-in embedding adapter, read-only search CLI and paired
retrieval comparison now have synthetic contract/HTTP checks; no learned encoder
has been run. Next, verify a local embedding model on development cases, freeze
its exact weights/runtime/threshold, then report evaluation cases and failures.
Drafting/UI retrieval remains lexical until measured results justify a change.
The October 23 run added removal of current contact-scoped database records,
including saved packets, all revisions and feedback, with preview and explicit
confirmation. SQLite index rebuilding preserves current records. Real-model
inference remains blocked by unavailable local setup; it was not replaced by
a synthetic quality claim. Large-history embedding indexing, tracking/removing
external exports and backups, automatic memory extraction, pagination and
real-user evaluation remain pending. No sending integration is planned for the
current review-only milestone.
