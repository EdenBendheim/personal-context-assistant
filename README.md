# Personal Context Assistant

A communication assistant that retrieves relevant conversation history and the owner's writing examples for a particular contact. The goal is a reviewable draft that sounds appropriate for the recipient and grounds factual claims in inspectable sources.

**Status — October 26, 2026:** working ingestion,
contact-scoped retrieval, editable memory and persistent draft review. Contact
removal now previews every stored copy in its scope, requires an unchanged plan
and explicit confirmation, and removes messages/memory/draft history atomically.
A local UI/CLI and verified SQLite index rebuild are available. External exports,
backups and physical storage remnants are not erased. Local-model adapters remain
synthetically checked only; real inference and reply quality are unverified.

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

### Optional embedding search

`embeddings.EmbeddingProvider` defines an explicit batch encoder interface.
`embed_validated` bounds inputs and checks one nonzero finite vector per text,
consistent dimensions and normalized cosine scoring. It preserves the caller's
input list. This module contains no learned model or network client; synthetic
vector checks are contract tests, not semantic retrieval or reply-quality results.

`semantic.EmbeddingSearch(store, provider)` is an opt-in cosine retriever with
the same source/participant/exclusive-cutoff result contract. It filters history
before encoding, rechecks sources afterward, retains outbound-only style examples,
and fails if more than 128 eligible messages would need encoding. It does not
silently truncate history or cache vectors. The lexical baseline remains unchanged.
Synthetic synonym vectors demonstrate routing/boundaries, not learned model quality.

`local_embeddings.OllamaEmbeddingProvider` implements this interface through
Ollama's [`POST /api/embed`](https://docs.ollama.com/api/embed). It requires an
explicit model name and confirmation that the local daemon has cloud disabled.
Only a literal loopback HTTP endpoint is allowed; there are no proxies, redirects,
model downloads or fallbacks. Requests disable input truncation, use bounded
timeouts, unload afterward and reject malformed/oversized responses. Tests use
a synthetic HTTP fixture. No real embedding model has been run or evaluated.

After importing the synthetic demo, an **already installed** embedding model can
be tried separately from the default lexical CLI. First configure your Ollama
daemon with cloud disabled; `--confirm-local-only` records your confirmation,
not an automated inspection of its settings. Replace `YOUR_INSTALLED_MODEL`:

```sh
PYTHONPATH=src python3 -m personal_context.embedding_cli 'demo' \
  --db data/demo.sqlite --model YOUR_INSTALLED_MODEL --confirm-local-only \
  --owner owner@example.invalid --contact alex@example.invalid \
  --before 2026-09-04T00:00:00Z --min-score 0.2
```

This opens an existing database read-only and prints source-bearing results plus
requested provider/threshold settings. It creates no database, persists no vectors
and returns an error without lexical fallback if inference fails. The default
threshold is untuned; cosine scores are not probabilities. Drafting and the review
UI still use lexical retrieval. Large-history batching/indexing remains pending.

### Compare retrieval on fixed cases

With the same already installed, cloud-disabled local embedding model:

```sh
PYTHONPATH=src python3 -m personal_context.retrieval_comparison \
  examples/benchmark/manifest.json --model YOUR_INSTALLED_MODEL \
  --confirm-local-only --split development --min-score 0.2
```

The paired report evaluates both backends on identical source records, cases,
cutoffs and limits. It retains the benchmark fingerprint, requested model/settings,
threshold, per-case missing/unexpected IDs, boundary violations and metric deltas.
It omits message bodies. Exit 1 means at least one backend missed an expected
result, returned an unexpected result or violated a boundary; inference/config
errors exit 2 without a successful report. Failed scores are not hidden.

Choose settings on development cases, freeze the configuration, then use
`--split evaluation`. Do not tune on evaluation results. Current checks use
handwritten synthetic vectors to exercise the comparison, including a worse
embedding result. They are not evidence of learned retrieval improvement. A real
run must additionally record the model weights/runtime; a requested model name
alone does not establish reproducibility or model identity. This benchmark does
not measure reply quality, style or factual entailment.

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

Withdrawal is an exclusion tombstone, **not permanent erasure**: history retains previous text, reasons, and source IDs for review. Current database removal is a separate explicit preview/confirmation workflow below; raw-export deletion remains planned. Memory is local SQLite data; keep its database in ignored `data/`. There is no automatic memory extraction or message sending.

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

`feedback_history` preserves earlier assessments. `summary(owner=..., contact=...)` counts only the latest assessment of each current draft revision whose source context is still current, so re-rating cannot inflate the sample and an edit needs a new rating. Deleted or edited sources and withdrawn memory exclude earlier ratings from current decision/retrieval/style/support totals. Separate `stale_context_reviews` and `stale_context_ratings` counts explain exclusions; feedback history remains inspectable. Memory changes refresh these counts in the browser. It also counts changed drafts and reports word multiset overlap against the original template. Overlap ignores word order; these subjective development measurements do not establish held-out reply quality. Empty samples report a null overlap.

## Local review API

```sh
export PYTHONPATH=src
python3 -m personal_context.review_server --db data/demo.sqlite \
  --owner owner@example.invalid --port 8765
```

The server requires an existing imported database, binds only to `127.0.0.1`, and prints its URL and a random per-launch bearer token to the local terminal. Requests use `Authorization: Bearer TOKEN`. Keep that token local. `GET /api/contacts` lists only this owner's conversations. `GET /api/reviews?contact=...`, `GET /api/reviews/ID`, and `GET /api/summary?contact=...` inspect saved work. `POST /api/reviews` takes contact/before/query and optional mode/limit; `/api/reviews/ID/edit` and `/feedback` use the fields described above. The owner is fixed at launch; a request cannot override it. `GET /api/reviews/page?contact=...` provides 25 saved reviews at a time (configurable `limit` from 1 to 100), topic/mode/revision metadata and an optional `next_cursor`. Supply that review ID as `cursor` for the next page. The cursor must belong to this owner/contact. Ordering uses creation time plus review ID, so new reviews do not shift an in-progress page. A removed cursor requires a list reload. The older `/api/reviews` route remains capped at 100 for compatibility.

Responses are uncached. Unexpected Host/Origin headers and unauthenticated API reads/writes are rejected; there is no cross-origin access. JSON bodies are bounded and each request uses its own SQLite connection. Conflicting edits/usable labels return HTTP 409. Traffic paths and message bodies are not logged. This local single-user server is not an internet deployment service. There is no sending endpoint.

## Review in the browser

Start the server using the command above and open the printed `http://127.0.0.1:PORT/` URL. The page obtains its API token from a per-launch, uncached bootstrap; no token goes in a URL or browser storage.

1. Select a contact, topic, exclusive ISO cutoff, and draft mode; create a review. Saved-review labels include their topic and revision; use **Load older reviews** to browse beyond the first page without discarding open or unsaved wording.
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

The review path now supports the default extractive baseline and an opt-in local generative provider. Next: verify an installed, cloud-disabled local model on synthetic messages, then evaluate semantic support and recipient/style preference on fixed reply cases before using real history. Embedding retrieval has a separate synthetic comparison; real-user reply quality and removal of external exports/backups remain pending.

## Generated wording contract (development API)

`personal_context.generation.generate(engine, request, provider)` accepts a separate
generative provider, leaving the extractive baseline unchanged. A proposal contains
up to 12 fact/social/question segments or an explicit abstention. Factual segments
must cite literal support from the retrieved evidence; outbound style examples
cannot serve as factual citations. Support and draft lengths are bounded. The
engine passes an isolated packet and rechecks source/memory state after generation.

All generated wording requires human semantic review. A real quote can support a
false paraphrase, and a model can mislabel a factual sentence as social/question
text. These structural checks do not establish entailment, truth, style imitation
or reply quality, and never authorize sending. No model service is called by this
contract alone.

The versioned `grounded-draft-v1` prompt puts instructions in a system message and
the selected packet/schema in a separate JSON data message. It distinguishes
historical evidence from outbound style examples and asks for abstention instead
of invented facts. The response parser rejects duplicate keys, extra fields,
markdown wrappers, nonfinite constants and oversized content. Prompt formatting
is not a demonstrated defense against model prompt injection; human review and
source checks still apply.

### Local model adapter

An opt-in `OllamaProvider(LocalModelConfig(...))` uses Ollama's
[structured chat API](https://docs.ollama.com/api/chat) and
[JSON-schema response format](https://docs.ollama.com/capabilities/structured-outputs).
The client accepts only literal `http://127.0.0.1:PORT`, uses no proxy or redirects,
limits prompt/response bytes, timeout and output tokens, and never pulls models.
It rejects incomplete/tool-call responses and never silently falls back to a
successful template if inference fails. Requested settings are retained with the
review; they do not verify the daemon's model weights.

Before enabling it, run Ollama with cloud disabled (`OLLAMA_NO_CLOUD=1`), choose
an already installed local model and explicitly confirm local-only setup. See
[Ollama's local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).
Loopback alone cannot prove that a separately managed daemon will not proxy data.
No actual model inference has been validated yet: current adapter checks use a
synthetic HTTP server, not an LLM or paid service.

Generated results can be persisted with `Reviews(store).create(request, provider=...)`.
Inference runs outside the SQLite writer transaction; context is revalidated
before saving. Abstentions and provider failures create no review. Original
segments, quotes and provider settings remain immutable through edits.

Generated reviews require `feedback(..., decision="usable", support="supported")`
for the exact current wording revision. Other support ratings are `needs_check`,
`unsupported` and `not_rated`; an edit needs a fresh assessment. This is the
person's recorded judgment, not an automatic entailment result or permission to
send. Existing feedback is migrated with `not_rated`, preserving its history.

### Enable local generation explicitly

Both `personal_context.draft_cli` and `personal_context.review_server` accept
`--local-model MODEL --confirm-local-only`, plus optional `--model-endpoint`,
`--model-timeout`, `--model-max-tokens` and `--model-seed`. Keep the usual
DB/owner/contact/topic/cutoff arguments. Without a model, the default remains the
extractive baseline. Model-only flags without a model are rejected. No service
is started, model installed, or cloud setting changed by these commands.

The review server fixes its provider at launch; browser requests cannot replace
it or specify another endpoint. Authenticated `GET /api/config` reports the active
mode and requested configuration. Inference outages return HTTP 503 and save no
review; explicit abstentions return `provider_abstained`, also without a saved
review. The support rating is accepted by the feedback endpoint. This prototype
server handles requests serially, so an inference request may occupy it until
completion or the configured socket timeout.

### Review generated wording in the browser

The mode badge identifies the active provider. A generated review shows every
segment, its provider-suggested kind, linked literal quotes, and requested model
configuration. Review social/question segments too: their labels do not rule
out unsupported claims. Source text is rendered as text, never inserted as HTML.

**Factual support of saved wording** starts unchecked. The usable option stays
disabled until the reviewer explicitly checks all saved wording against sources;
the API enforces the same requirement. Saving an edit resets this assessment and
explains that the segment list still describes the original model draft. Earlier
revision assessments remain in history but do not approve the new wording.
Provider abstentions display a reason without creating an empty review. No
sending control or integration has been added.


## Scripted drafting regression suite

```sh
PYTHONPATH=src python3 -m personal_context.generation_evaluation examples/drafting/manifest.json
```

Thirteen fixed, invented cases check generated-response parsing, citation
availability, contact/time exclusions, abstention and cold starts. Every generated
wording result must require human support review. CI runs this separately from
the unchanged 20-case retrieval benchmark. The manifest/message bytes have a
reported SHA-256; reports omit message bodies and generated wording.

This suite supplies scripted responses, not language-model predictions. All 13
contract cases currently pass. Two intentionally contradicted wordings still
reach human review: a false paraphrase citing a real quote and a factual claim
mislabeled as social. These are explicit limitations, not semantic-check success.
Fixture labels come from the author; elapsed times measure infrastructure only.
No installed Ollama binary/service or cloud-disabled local setup was available
at the October 17 check, so no actual model inference or style-quality result is
claimed. Nothing was downloaded and no paid service was used.

## Preview contact data removal

`Privacy(store).preview(owner=..., contact=...)` in `personal_context.privacy`
returns counts and a snapshot-bound `plan_sha256` without message text. It
accounts for all stored revisions and packet copies in this contact scope,
including drafts that no longer match current sources. Retained source copies
in another scope block removal instead of deleting another owner's records.
Unknown application tables, incomplete schema groups or pending writes are
refused. Preview works with `Store(path, readonly=True)` and writes nothing.
`Privacy(store).apply(owner=..., contact=..., expected_plan_sha256=...,
confirm=True)` rechecks the exact plan under a writer transaction and removes
all selected live records atomically. Any store change requires a new preview;
other-scope copies block applying. Pending caller writes are never committed.
SQLite secure delete is enabled for the operation and restored afterward.
This does not remove external exports,
backups, browser copies or provider logs and cannot guarantee physical erasure.

### Preview-first privacy CLI

```sh
PYTHONPATH=src python3 -m personal_context.privacy_cli --db data/demo.sqlite \
  --owner owner@example.invalid --contact alex@example.invalid
```

To remove the reviewed current database records, repeat those arguments with
`--apply-plan EXACT_PLAN_SHA256 --confirm-delete`. A stale plan fails without
removal; preview and review again. Both the digest and confirmation are required.
Missing stores are never created and the CLI never unlinks source exports.
There is no undo in this store after commit. Reimport can restore data, so manage
original exports and backups separately. This CLI makes no physical-erasure claim.

### Rebuild the local SQLite indexes

```sh
PYTHONPATH=src python3 -m personal_context.maintenance \
  --db data/demo.sqlite --rebuild-indexes
```

This existing-store-only command runs integrity checks before and after
`REINDEX`, within a writer transaction. Application rows and their privacy-plan
fingerprint must remain identical; failures roll back. It works after contact
removal and does not restore deleted records. This is SQLite maintenance, not
vector-index rebuilding: embedding search currently retains no persistent index.
It does not compact the file or delete exports/backups/storage remnants.

### Remove contact data in the local workspace

Choose **Preview removal** to inspect counts. Removal stays disabled until you
type the selected contact’s full identifier. A final confirmation explains the
irreversible database action. Changing contacts or making another local write
clears the preview; server-side snapshot checks also reject concurrent changes.
After success the page reloads, dropping its rendered packets and refreshing
contacts. No messages are sent. Another already-open tab may still display copies.

Authenticated `GET /api/privacy?contact=...` returns the preview;
`POST /api/privacy/remove` requires `contact`, `expected_plan_sha256` and literal
`confirm: true`. The owner is fixed at server launch, not supplied by the request.
Contacts with only saved drafts or memory remain selectable even if raw messages
are already missing. Other-scope cited copies block removal. Uncited free-text
copies elsewhere cannot be detected; manage those and original exports separately.

Synthetic checks cover full-copy removal, owner/auth boundaries, stale plans,
blocked shared sources and contacts with orphaned saved copies. A real browser
check verified preview counts, typed-identifier gating and clearing on contact
switch; no personal data was used or removed. This does not demonstrate model
quality or guaranteed physical erasure.
