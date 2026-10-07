# Personal Context Assistant

A communication assistant that retrieves relevant conversation history and the owner's writing examples for a particular contact. The goal is a reviewable draft that sounds appropriate for the recipient and grounds factual claims in inspectable sources.

**Status — October 6, 2026:** working export ingestion, import preview/error reporting, contact-specific retrieval, a fixed synthetic benchmark, editable memory, and a local extractive draft/review pipeline with persistent edits, feedback, and a browser review workspace. A local browser review UI now works; language-model drafting and embedding retrieval are planned. No personalized language model has been trained.

## Working now

- Normalized JSONL, plain-text Gmail/standard MBOX, and outbound Discord export CSV ingestion.
- SQLite persistence, provider-ID and normalized-content deduplication, and atomic imports.
- Lexical retrieval restricted to the selected pair of participants, with an exclusive timestamp cutoff to prevent future conversation leakage.
- A separate view of the owner's outbound style examples, rather than treating another person's writing as the owner's style.
- Source, message ID, thread, participants, and timestamp retained on every retrieved result.
- Import preview counts valid, invalid, skipped, and duplicate records across JSONL, MBOX, and Discord CSV. Invalid files are rejected before any database writes.
- A versioned benchmark with disjoint development/evaluation conversations, source labels, exclusive cutoffs, and future/cross-contact distractors. CI fails on missing expected context or boundary violations.
- Human-reviewed facts/preferences scoped to one contact, with cited immutable revisions, correction history, explicit withdrawal, and stale-editor protection.
- Generic, context-only, and personalized review packets; a deterministic extractive provider, literal-quote citation checks, insufficient-history handling, and context-change detection before returning a draft.

This first retrieval baseline deliberately needs no API key, model download, or external service. It provides a measurable comparison for the embedding-based version.

## Try the synthetic demo

Python 3.11+; no runtime dependencies. All demo participants and messages are invented.

```sh
export PYTHONPATH=src
python3 -m personal_context.cli --db data/demo.sqlite import examples/synthetic.jsonl --preview
python3 -m personal_context.cli --db data/demo.sqlite import examples/synthetic.jsonl
python3 -m personal_context.cli --db data/demo.sqlite search demo \
  --owner owner@example.invalid --contact alex@example.invalid \
  --before 2026-09-04T00:00:00Z
python3 -m personal_context.cli --db data/demo.sqlite style \
  --owner owner@example.invalid --contact alex@example.invalid \
  --before 2026-09-04T00:00:00Z
python3 -m unittest discover -s tests -v
```

Reimporting the fixture inserts zero additional messages. The October message is excluded by the cutoff; Riley's conversation never enters Alex's context.

## Preview before importing

`import --preview` does not create the database or its parent directory. An existing SQLite database is opened read-only to check provider IDs and normalized fingerprints. Reports expose counts and record-level reasons, not message bodies. JSONL/CSV record numbers are physical lines; MBOX numbers identify mail items (one mail can produce multiple directed messages).

If any record is invalid, both preview and regular import exit with status 2 and regular import inserts nothing. `would_insert` shows valid nonduplicate candidates, not a partial import that will be applied. Unsupported HTML-only MBOX items, blank JSONL lines, and empty outbound Discord messages are counted as skipped. A successful regular import reports its actual `inserted` count. Counts reflect an inspection snapshot; concurrent changes can affect the number finally inserted. This version materializes candidate messages in memory, so very large exports need a later streaming/staging implementation.

## Import contract

JSONL requires string fields `id`, `source`, `thread`, `author`, `recipient`, `timestamp`, and `body`. Timestamps must carry a timezone. Each record describes one directed message. Participant identifiers are case-folded; use stable account identifiers rather than display names.

MBOX import skips HTML-only mail and attachments. It emits one record per `To` recipient and uses `X-GM-THRID` or the first `References` ID when available. Other mail headers, group-chat membership, rich text, and HTML conversion are outside this first version. Quote cleanup is a heuristic and should be inspected when building an evaluation set.

Discord CSV import expects `ID`, `Timestamp`, and `Contents`, with explicit `--owner`, `--contact`, and `--thread`. The account's export contains its own messages; this importer does not invent missing incoming messages. Naive Discord export timestamps are treated as UTC. Prefer normalized JSONL if your export differs.

Real exports belong in ignored `exports/` or `data/` directories. Only synthetic fixtures belong in the public repository. The CLI imports local files and displays context; it has no message-sending integration.

## Run the fixed retrieval benchmark

```sh
export PYTHONPATH=src
python3 -m personal_context.evaluation examples/benchmark/manifest.json
python3 -m personal_context.evaluation examples/benchmark/manifest.json --split development
```

The fixture contains **31 invented messages in seven conversations**, with six development cases and 14 held-out evaluation cases. Cases specify the owner, contact, conversation, cutoff, query, expected source/message pairs, expected outbound examples, and forbidden records. The benchmark includes a contact with only incoming history and a case with no history before the cutoff. It uses an in-memory database and needs no private export, provider, or API key.

Reports include per-case recall/precision, missing source IDs, outbound-example coverage, boundary violations, and a SHA-256 fingerprint of the manifest plus fixture. Empty relevant sets have undefined recall (`null`); returning nothing scores precision 1 only when nothing is relevant. Aggregate recall averages cases with positive labels. Reports omit message bodies. The command exits 1 for a retrieval regression; CI runs both partitions with `--split all`.

The current lexical baseline retrieves all labeled context with no boundary violations on this small fixture. These are transparent regression cases, not a blind real-user study or evidence that generated replies sound like anyone. The conversation partitions are for future fitting/comparisons; this baseline performs no training. Growing a sufficiently diverse reply benchmark and evaluating drafting quality remain necessary.

## Evaluation direction

Compare generic drafting, lexical context, embedding context, and contact-specific examples on the same held-out reply situations. Split by thread and time. Track source support, recipient/style preference in blinded comparisons, useful edits, latency, and cost. A low retrieval loss alone does not establish that drafts are better.

## Review and edit cited memory

Memory is an explicitly reviewed fact or preference, not an automatically extracted claim. Each active revision must cite at least one existing `(source, message_id)` in the exact owner/contact conversation. The store pins each source's content fingerprint; removed or changed messages invalidate the memory in context. Provenance records let a person inspect support; they do not automatically prove that a sentence follows from its citations.

Run the complete synthetic correction/withdrawal walkthrough without writing a database:

```sh
export PYTHONPATH=src
python3 -m personal_context.memory_demo
```

For a local database imported using the earlier demo commands:

```sh
python3 -m personal_context.memory_cli --db data/demo.sqlite add \
  --owner owner@example.invalid --contact alex@example.invalid --kind fact \
  --text 'The Thursday demo should include a retrieval example.' \
  --source gmail 1 --source gmail 2 --reason 'Reviewed the demo discussion'
python3 -m personal_context.memory_cli --db data/demo.sqlite list \
  --owner owner@example.invalid --contact alex@example.invalid \
  --before 2026-10-05T00:00:00Z
```

The add/list result contains `memory_id` and `revision`. Use that ID with `history ID`, `update ID --expected-revision N --text ... --source PROVIDER ID --reason ...`, or `revoke ID --expected-revision N --reason ...`. Update/revoke require the revision the editor reviewed; a concurrent newer revision is rejected. Edits are atomic and do not commit unrelated pending message changes. Scope and kind are immutable; a revoked item cannot be restored through update. Create a new reviewed item if necessary.

Revisions default to the current UTC time; `--at` supplies an explicit timezone-aware effective time for imported history or controlled evaluations. Supporting messages cannot be later than their revision, and revision times must increase strictly. Context chooses the latest revision **strictly before** `--before`, so a later correction cannot leak backward. Withdrawal overrides historical retrieval too, preventing reuse of a memory the owner has explicitly withdrawn.

Withdrawal is an exclusion tombstone, **not permanent erasure**: history retains previous text, reasons, and source IDs for review. Raw-export deletion and privacy erasure remain planned. Memory is local SQLite data; keep its database in ignored `data/`. There is no automatic memory extraction or message sending.

## Build a draft for review

```sh
export PYTHONPATH=src
python3 -m personal_context.draft_demo
python3 -m personal_context.draft_cli --db data/demo.sqlite \
  --owner owner@example.invalid --contact alex@example.invalid \
  --before 2026-09-04T00:00:00Z --query demo --mode personalized
```

The demo uses invented messages in memory. The CLI reads an existing imported store; it does not create a missing database or send anything. Reports contain `draft_text`, `citations`, an inspectable `packet`, its fingerprint, review notes, and a status:

- `generic`: a template using the supplied topic; no conversation or memory retrieval.
- `context`: matching past messages from the selected participant pair.
- `personalized`: matching messages plus reviewed, valid memory and the owner's outbound writing examples for that contact. These examples are available to the provider, but the current extractive provider does not imitate their style.
- `needs_history`: contextual/personalized mode has no factual evidence, even if style-only examples exist. The provider is not called and the draft is empty.
- `needs_review`: a template with at most three labeled historical quotes and a place for the person to add a response or next step. This status does not mean ready to send.

`QuoteProvider` accepts an isolated copy of the review packet and returns `CitedQuote` selections. Unknown references, style-only citations, nonliteral quotes, duplicates, and oversized proposals are rejected. Each quote retains message provenance or a memory revision with its supporting source IDs. The engine rebuilds the packet after provider selection: source edits, withdrawals, or changed retrieval during that call require a new review. The fixed retrieval benchmark remains unchanged; drafting has separate synthetic development tests and a CI walkthrough.

This is an **extractive template baseline**, not a generative reply model. Literal matching establishes where a quote came from; it does not prove that a truncated quote preserves meaning, that old information is still true, or that a reviewed memory is entailed by its sources. A language-model provider needs additional semantic support checks and reply-quality evaluation. There is no API request or paid service. Reports include message bodies and memory text, so real output belongs in ignored `drafts/`, `runs/`, or `data/`, never a public fixture.

See [PLAN.md](PLAN.md) for milestones and [DEVLOG.md](DEVLOG.md) for actual completed work.

## Save and revisit draft reviews

`Reviews(store).create(DraftRequest(...))` saves a generated packet and its original citations in the local SQLite store. `get(id, owner=...)`, `edit(id, owner=..., expected_revision=N, text=...)`, `history(id, owner=...)`, and `list(owner=..., contact=...)` provide owner-scoped access. Edits preserve whitespace, the immutable original, and earlier wording. A stale editor is rejected; saving unchanged wording adds no revision. A cold-start result is returned without saving an empty review.

Each loaded review reports `context_current`: the same contact/topic/cutoff packet is rebuilt and compared with the original fingerprint. Saved history remains inspectable when source content changes; it is not permanently erased. Private drafts remain in the ignored database, and saving is not sending. The browser interface below uses this persistence layer.

### Record feedback on the wording you reviewed

`feedback(id, owner=..., expected_revision=N, decision="usable"|"needs_work"|"rejected", retrieval="useful"|"incorrect"|"not_rated", style="appropriate"|"needs_edit"|"not_rated", notes="...")` records a local assessment. Marking stale-context drafts usable is rejected; rejection/needs-work feedback still helps diagnose failures. This is a review label, not sending or automatic factual validation of edited prose.

`feedback_history` preserves earlier assessments. `summary(owner=..., contact=...)` counts only the latest assessment of each current draft revision, so re-rating cannot inflate the sample and an edit needs a new rating. It also counts changed drafts and reports word multiset overlap against the original template. Overlap ignores word order; these subjective development measurements do not establish held-out reply quality. Empty samples report a null overlap.

## Local review API

```sh
export PYTHONPATH=src
python3 -m personal_context.review_server --db data/demo.sqlite \
  --owner owner@example.invalid --port 8765
```

The server requires an existing imported database, binds only to `127.0.0.1`, and prints its URL and a random per-launch bearer token to the local terminal. Requests use `Authorization: Bearer TOKEN`. Keep that token local. `GET /api/contacts` lists only this owner's conversations. `GET /api/reviews?contact=...`, `GET /api/reviews/ID`, and `GET /api/summary?contact=...` inspect saved work. `POST /api/reviews` takes contact/before/query and optional mode/limit; `/api/reviews/ID/edit` and `/feedback` use the fields described above. The owner is fixed at launch; a request cannot override it.

Responses are uncached. Unexpected Host/Origin headers and unauthenticated API reads/writes are rejected; there is no cross-origin access. JSON bodies are bounded and each request uses its own SQLite connection. Conflicting edits/usable labels return HTTP 409. Traffic paths and message bodies are not logged. This local single-user server is not an internet deployment service. There is no sending endpoint.

## Review in the browser

Start the server using the command above and open the printed `http://127.0.0.1:PORT/` URL. The page obtains its API token from a per-launch, uncached bootstrap; no token goes in a URL or browser storage.

1. Select a contact, topic, exclusive ISO cutoff, and draft mode; create a review.
2. Inspect historical message/memory snippets, source provenance, and separate outbound writing examples.
3. Edit and save wording. Unsaved wording must be saved before rating; conflicting editors require a reload.
4. Record a decision plus retrieval/style feedback. Reopen the saved review after a restart to inspect revisions and earlier ratings.

Contact changes and navigation protect unsaved wording. The interface uses text nodes for message content, a restrictive content-security policy, no external assets, and a responsive layout. A changed-context review cannot be marked usable until rebuilt. Citations still describe the original extractive quotes; they do not automatically validate your edited prose. Cited memory can be created, corrected, and withdrawn in the same workspace.

### Edit memory in the workspace

Create a draft with source history, then choose supporting messages in **Reviewed memory**, write a fact/preference and a reason, and save. Select an existing item to inspect its revisions and current supporting message text, correct its wording/citations, or withdraw it with a reason. The selected kind/contact stays fixed. Source text is inspected only within the owner's exact conversation; a removed, changed, or moved source is marked unavailable/invalid.

Browser edits use the real current time and expected revision numbers. The panel distinguishes the latest editable revision from the revision eligible at the selected draft cutoff. Use **Use current time as draft cutoff** and create a new review to include a new correction. Withdrawal also suppresses historical reuse and marks affected saved draft context stale. The immutable saved packet and memory audit still retain previous text; withdrawal is not erasure. The interface lists the latest 100 memory items/reviews per contact; history is unpaginated in this prototype.

API equivalents: `GET /api/memory?contact=...&before=...`, `GET /api/memory/ID`, `POST /api/memory` with contact/kind/text/sources/reason, `POST /api/memory/ID/edit` with expected_revision/text/sources/reason, and `POST /api/memory/ID/withdraw` with expected_revision/reason. Sources are `[provider, message_id]` pairs. The owner is always the launch owner.

### Architecture and next work

Local exports → normalized SQLite messages → contact/time-limited retrieval + reviewed memory → immutable cited draft packet → saved wording revisions → human feedback. The browser talks only to the local owner-scoped API. No external scripts or message-send integration are involved.

The usable review path is now implemented. Next: a language-model provider with semantic-support evaluation, followed by embedding retrieval comparisons on fixed splits. The current provider still produces an extractive template, not learned style imitation. Real-user reply quality and permanent privacy erasure remain unimplemented.
