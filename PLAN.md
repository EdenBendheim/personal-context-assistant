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

- [ ] Build a small review interface: selected contact, source snippets, editable memory, draft editing, feedback.
- [ ] Add explicit local export deletion and index rebuild.
- [x] Record useful/incorrect retrievals and changed wording without sending messages automatically.
- [ ] Publish a synthetic walkthrough and architecture explanation.

## Milestone 4 — measured results

- [ ] Approximately 50 held-out reply situations, subject to suitable data availability.
- [ ] Blind style/preference comparison with generic drafting, factual support, edits, latency/cost.
- [ ] Report failure examples and uncertainty, not only successful screenshots.
- [ ] Consider a style adapter only if retrieval/prompting plateau and the dataset supports a clean evaluation.

## Next session

Build a small local review UI over the existing draft packets: select a contact/topic/cutoff, inspect citations and memory, edit the reply, and record feedback without sending. Add a language-model provider with an explicit semantic-support contract after that review path works; the current literal-quote provider cannot validate free-form factual prose or imitate style. Keep the fixed retrieval benchmark unchanged and extend separate drafting development cases. Embedding retrieval, permanent privacy erasure, automatic memory extraction, and real-user reply-quality evaluation remain pending. Keep a short explanation of each actual change and its checks in DEVLOG. The daily development run implements, checks, commits, and pushes an update; small useful steps are sufficient.
