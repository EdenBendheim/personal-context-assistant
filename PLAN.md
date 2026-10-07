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

- [ ] Add an embedding backend behind the same retrieval contract; retain lexical baseline.
- [x] Add an extractive quote-provider contract and an inspectable draft packet with citations.
- [x] Separate generic, context-only, and personalized context configurations.
- [x] Reject unavailable/nonliteral quotes and stale context; abstain when factual history is insufficient.
- [ ] Add a language-model draft provider using retrieved citations and recipient examples.
- [ ] Add semantic support checks for generated factual prose and evaluate style/reply quality.

## Milestone 3 — useful application

- [x] Add a loopback HTTP review API with a fixed owner, per-launch authorization, bounded requests, and integration checks.
- [x] Persist original draft packets and immutable wording revisions with owner isolation and stale-editor checks.

- [x] Build contact selection, source inspection, draft editing/reopening, and feedback in a local review interface.
- [x] Add cited-memory creation/correction/withdrawal to that browser interface.
- [ ] Add explicit local export deletion and index rebuild.
- [x] Record useful/incorrect retrievals and changed wording without sending messages automatically.
- [x] Publish synthetic demo commands, a browser walkthrough, and an architecture explanation.

## Milestone 4 — measured results

- [ ] Approximately 50 held-out reply situations, subject to suitable data availability.
- [ ] Blind style/preference comparison with generic drafting, factual support, edits, latency/cost.
- [ ] Report failure examples and uncertainty, not only successful screenshots.
- [ ] Consider a style adapter only if retrieval/prompting plateau and the dataset supports a clean evaluation.

## Next session

The local review path now supports contact/topic/cutoff selection, source and memory inspection, draft editing/reopening, revision-bound feedback, and cited-memory creation/correction/withdrawal. Add a language-model provider with an explicit semantic-support contract and separate synthetic drafting cases. Compare its useful edits and source support against this extractive template before claiming style imitation. Keep the fixed retrieval benchmark unchanged. Embedding retrieval, permanent privacy erasure (including saved packet copies), automatic memory extraction, large-history pagination, and real-user reply-quality evaluation remain pending. Keep DEVLOG factual; small coherent verified daily steps are enough.
