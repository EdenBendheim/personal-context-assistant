# Personal Context Assistant

A communication assistant that retrieves relevant conversation history and the owner's writing examples for a particular contact. The goal is a reviewable draft that sounds appropriate for the recipient and grounds factual claims in inspectable sources.

**Status — October 3, 2026:** working export ingestion, read-only import preview/error reporting, contact-specific retrieval, and a fixed synthetic retrieval benchmark. Reply generation, embedding retrieval, editable memory, and the review UI are planned. No personalized language model has been trained.

## Working now

- Normalized JSONL, plain-text Gmail/standard MBOX, and outbound Discord export CSV ingestion.
- SQLite persistence, provider-ID and normalized-content deduplication, and atomic imports.
- Lexical retrieval restricted to the selected pair of participants, with an exclusive timestamp cutoff to prevent future conversation leakage.
- A separate view of the owner's outbound style examples, rather than treating another person's writing as the owner's style.
- Source, message ID, thread, participants, and timestamp retained on every retrieved result.
- Import preview counts valid, invalid, skipped, and duplicate records across JSONL, MBOX, and Discord CSV. Invalid files are rejected before any database writes.
- A versioned benchmark with disjoint development/evaluation conversations, source labels, exclusive cutoffs, and future/cross-contact distractors. CI fails on missing expected context or boundary violations.

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

See [PLAN.md](PLAN.md) for milestones and [DEVLOG.md](DEVLOG.md) for actual completed work.
