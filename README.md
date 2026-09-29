# Personal Context Assistant

A communication assistant that retrieves relevant conversation history and the owner's writing examples for a particular contact. The goal is a reviewable draft that sounds appropriate for the recipient and grounds factual claims in inspectable sources.

**Status — September 29, 2026:** working export-ingestion and retrieval foundation. Reply generation, embedding retrieval, editable memory, and the review UI are planned. No personalized language model has been trained.

## Working now

- Normalized JSONL, plain-text Gmail/standard MBOX, and outbound Discord export CSV ingestion.
- SQLite persistence, provider-ID and normalized-content deduplication, and atomic imports.
- Lexical retrieval restricted to the selected pair of participants, with an exclusive timestamp cutoff to prevent future conversation leakage.
- A separate view of the owner's outbound style examples, rather than treating another person's writing as the owner's style.
- Source, message ID, thread, participants, and timestamp retained on every retrieved result.

This first retrieval baseline deliberately needs no API key, model download, or external service. It provides a measurable comparison for the embedding-based version.

## Try the synthetic demo

Python 3.11+; no runtime dependencies. All demo participants and messages are invented.

```sh
export PYTHONPATH=src
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

## Import contract

JSONL requires string fields `id`, `source`, `thread`, `author`, `recipient`, `timestamp`, and `body`. Timestamps must carry a timezone. Each record describes one directed message. Participant identifiers are case-folded; use stable account identifiers rather than display names.

MBOX import skips HTML-only mail and attachments. It emits one record per `To` recipient and uses `X-GM-THRID` or the first `References` ID when available. Other mail headers, group-chat membership, rich text, and HTML conversion are outside this first version. Quote cleanup is a heuristic and should be inspected when building an evaluation set.

Discord CSV import expects `ID`, `Timestamp`, and `Contents`, with explicit `--owner`, `--contact`, and `--thread`. The account's export contains its own messages; this importer does not invent missing incoming messages. Naive Discord export timestamps are treated as UTC. Prefer normalized JSONL if your export differs.

Real exports belong in ignored `exports/` or `data/` directories. Only synthetic fixtures belong in the public repository. The CLI imports local files and displays context; it has no message-sending integration.

## Evaluation direction

Compare generic drafting, lexical context, embedding context, and contact-specific examples on the same held-out reply situations. Split by thread and time. Track source support, recipient/style preference in blinded comparisons, useful edits, latency, and cost. A low retrieval loss alone does not establish that drafts are better.

See [PLAN.md](PLAN.md) for milestones and [DEVLOG.md](DEVLOG.md) for actual completed work.
