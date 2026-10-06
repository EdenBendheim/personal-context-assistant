# Personal Context Assistant

A communication assistant that retrieves relevant conversation history and the owner's writing examples for a particular contact. The goal is a reviewable draft that sounds appropriate for the recipient and grounds factual claims in inspectable sources.

**Status — October 5, 2026:** working export ingestion, import preview/error reporting, contact-specific retrieval, a fixed synthetic benchmark, editable memory, and a local extractive draft/review pipeline. Language-model drafting, embedding retrieval, and the review UI are planned. No personalized language model has been trained.

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
