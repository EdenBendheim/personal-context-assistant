# Explicit reply tasks — November 9, 2026

The assistant now accepts an incoming message and a reply goal, retains exact
abstention reasons, and saves the task with the review packet. A paired local
7B development diagnostic produced **one draft requiring review out of nine
explicit-task attempts**, versus **zero out of nine topic-only attempts**. Eight
explicit-task attempts still abstained. This does not establish useful or
owner-style generation.

## What changed

`DraftRequest.current_message` is optional, at most 2,000 characters;
`DraftRequest.intent` is optional, at most 500. Both are bounded nonempty text
when supplied. They are saved and fingerprinted but do not become evidence or
valid citation keys. Omitting them preserves old packet wire shapes and hashes;
historical saved reviews remain current when their sources remain current.

The v4 model prompt distinguishes the incoming message, reply goal and lexical
retrieval query. It permits acknowledgments/questions without inventing new
facts and explicitly warns against treating task input as evidence. Strict JSON,
literal-citation, stale-context and human support-review requirements remain.
The deterministic extractive baseline saves the task fields but keeps its
historical template; it does not synthesize a response from the goal.

The CLI accepts `--current-message` and `--intent`. The authenticated review API
accepts those optional fields; the browser can enter them, reopen a saved task,
and clears them on contact changes. Unsaved task edits participate in contact/
review-switch confirmation. A real browser created and reopened an invented
review after reload, restored both fields, and cleared them when switching
contacts. The temporary UI server was stopped. No user messages were used.

Provider abstentions now include a bounded `abstain_reason` field. Reply-study
reports preserve that field and review notes and count exact reasons. A refusal
still saves no fake draft or usable rating.

## Declared development comparison

The [fixture and protocol](../examples/reply_intent_development/PROTOCOL.md) and
runner were committed in `bd8c9594be8bd882542a70c9b3d3520a53d5beda` before actual
outcomes. Three **development** conversations reuse six invented workshop,
export and ticket messages from the earlier followup study. The added current
messages and goals are authored development inputs, not new factual sources.
No new model calls used evaluation conversations.

Both variants use v4, the same Qwen2.5 7B weights, seed 29, temperature zero,
512-token cap, 60-second timeout, modes and lexical window-1 source order.
Only the current-message/intent fields differ. Consequently this comparison
isolates those fields within v4; it does not isolate the v3-to-v4 prompt change
from the earlier study.

The [exclusive declaration](reply-intent-2026-11-09/declaration.json) binds the
fixture, both request variants, source fingerprint, prompt and provider identity.
The [model receipt](reply-intent-2026-11-09/model-identity.json) verifies the exact
installed model, runtime metadata and every local blob. The task-scoped Ollama
0.40.13 daemon had `OLLAMA_NO_CLOUD=true`; no model was pulled or paid API used.
All 18 raw proposal strings remain in ignored local files. The daemon was
stopped after the comparison.

## Outcomes and inspection

[All synthetic outcomes and reasons](reply-intent-2026-11-09/results.json)

| Input | Actual model calls | Abstentions | Drafts requiring review | Rejections |
|---|---:|---:|---:|---:|
| Topic only | 9 | 9 | 0 | 0 |
| Current message + reply goal | 9 | 8 | 1 | 0 |

Many refusals still say “No new facts” or “No new information,” even where the
request asks for an acknowledgment or question. The new fields do not resolve
most of this behavior.

The only accepted *structural* response is the workshop/context case:

> Of course, the workshop is confirmed for 2 pm in room 12.

It cites the incoming history line “It starts at 2 pm in room 12.” The time and
room match the source. However, “confirmed” adds assurance beyond that wording,
and the draft omits the requested thanks. It remains unapproved and needs
human wording/support review. This inspection is an assistant observation,
not a blind human factual/usefulness rating or an automated entailment score.
The personalized workshop mode still abstained.

All paired cases returned identical source IDs. Draft counts alone are not
quality metrics. Three authored development situations do not establish
held-out generalization, preference, style imitation or a useful product result.
No prompt, model, threshold or validation rule was changed after viewing outcomes
in this diagnostic.

## Commands and next work

For an already installed model on a separately verified cloud-disabled local
daemon, declare before running. Replace `EXACT_DIGEST` with its checked SHA-256:

```sh
PYTHONPATH=src python3 -m personal_context.intent_comparison declare \
  examples/reply_intent_development/manifest.json runs/my-intent/freeze.json \
  --local-model qwen2.5:7b --expected-model-digest EXACT_DIGEST \
  --confirm-local-only --model-timeout 60 --model-max-tokens 512

PYTHONPATH=src python3 -m personal_context.intent_comparison run \
  examples/reply_intent_development/manifest.json runs/my-intent/freeze.json \
  --output runs/my-intent/results.json \
  --local-model qwen2.5:7b --expected-model-digest EXACT_DIGEST \
  --confirm-local-only --model-timeout 60 --model-max-tokens 512
```

Use the declared source revision and settings. Existing receipts/results are
not overwritten. This command refuses evaluation cases and does not choose
settings. Prompt size still has the local provider's 6,000-byte bound; reduce
retrieved context if a request exceeds it.

Next investigate persistent refusal on development inputs, distinguishing
prompt interpretation from constrained-output behavior. Keep the validation
and human review gates, retain unsuccessful outputs, and collect actual human
support/usefulness ratings before a separate frozen held-out study. Larger
models, source coverage and a single new sentence have not yet established
useful personalized replies. Private history, real-user evaluation and external
export tracking remain separate unfinished work.

Verification: 155 local tests, the 20-case unchanged lexical retrieval regression,
13 scripted generation contracts, source-label validation, memory/draft demos,
JavaScript syntax and whitespace checks pass. Those scripted checks test
contracts, not model quality. Earlier experiment artifacts remain unchanged.

Interview explanation: “I added explicit reply tasks and retained the model's
reasons for refusing, then compared the change on identical sources while
keeping every generated draft subject to factual and wording review.”
