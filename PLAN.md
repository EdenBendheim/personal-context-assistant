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
- [ ] Add a configurable draft provider using retrieved citations and recipient examples.
- [ ] Separate generic, context-only, and personalized configurations.
- [ ] Add unsupported-fact checks and graceful handling of insufficient history.

## Milestone 3 — useful application

- [ ] Build a small review interface: selected contact, source snippets, editable memory, draft editing, feedback.
- [ ] Add explicit local export deletion and index rebuild.
- [ ] Record useful/incorrect retrievals and changed wording without sending messages automatically.
- [ ] Publish a synthetic walkthrough and architecture explanation.

## Milestone 4 — measured results

- [ ] Approximately 50 held-out reply situations, subject to suitable data availability.
- [ ] Blind style/preference comparison with generic drafting, factual support, edits, latency/cost.
- [ ] Report failure examples and uncertainty, not only successful screenshots.
- [ ] Consider a style adapter only if retrieval/prompting plateau and the dataset supports a clean evaluation.

## Next session

Add a reviewable draft contract that combines retrieved messages, current cited memory, and outbound examples. Start with a deterministic synthetic provider so unsupported-fact and insufficient-history checks work without paid APIs; then add configurable providers and embedding retrieval behind the same contract. Keep the fixed retrieval benchmark unchanged and add separate drafting cases. The current memory API/CLI works, but automatic extraction, permanent privacy erasure, draft generation, style quality, and a review UI remain pending. Keep a short explanation of each actual change and its checks in DEVLOG. The daily development run implements, checks, commits, and pushes an update; small useful steps are sufficient.
