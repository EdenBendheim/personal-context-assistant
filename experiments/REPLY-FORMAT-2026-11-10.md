# Reply decoder diagnostic — November 10, 2026

Removing Ollama's decoder schema constraint changed the output on three
synthetic development conversations. The constrained arm produced eight
abstentions and one draft requiring review. The prompt-only arm produced seven
drafts requiring review and two citation rejections. Inspection found additional
claims and missed reply goals among the drafts. Useful personalized generation
still requires further work and human evaluation.

## Method

The [protocol](../examples/reply_intent_development/FORMAT_PROTOCOL.md) and runner
were committed in `cd87b2b0e00ceed34776393792763c71aac7867a` before outcomes.
The study reused the November 9 workshop, export and ticket development cases,
each in generic, context and personalized modes. All inputs use invented
participants and messages. Each case supplied its current message and reply goal.

Both arms used the same v4 prompt, Qwen2.5 7B digest, seed 29, temperature zero,
512-token output cap, 60-second timeout and lexical window-1 retrieval. The
schema arm supplied the production JSON schema in Ollama's `format` parameter.
The prompt-only arm omitted that parameter. Both prompts included the exact same
JSON schema and instructions. Every paired prompt hash and retrieved source list
matched. The strict JSON parser, literal-citation checks and human review gate
applied to both arms.

The [declaration](reply-format-2026-11-10/declaration.json) binds source, fixture,
prompt, model/runtime and settings. The [model receipt](reply-format-2026-11-10/model-identity.json)
verifies all installed model blobs. The task-owned Ollama 0.40.13 process used
`OLLAMA_NO_CLOUD=1`. It made 18 actual requests and was stopped afterward.
Raw proposal strings remain in ignored local storage. This run used installed
weights, local compute and synthetic inputs.

## Outcomes

[Complete synthetic reports, reasons and prompt hashes](reply-format-2026-11-10/results.json)

| Decoder format | Model calls | Abstentions | Drafts requiring review | Citation rejections |
|---|---:|---:|---:|---:|
| Schema constraint | 9 | 8 | 1 | 0 |
| Schema in prompt only | 9 | 0 | 7 | 2 |

The schema arm reproduced the previous explicit-task outcomes. Many abstention
reasons still mention having no new facts. Removing the constraint affected
that behavior, while the model's internal reason for the change remains unknown.
All prompt-only outputs parsed as proposal JSON. The two rejections came from
invalid evidence references.

Assistant inspection found these issues. Human support and usefulness ratings
remain pending.

| Attempt | Inspection |
|---|---|
| Schema workshop/context and prompt-only workshop/personalized | Adds “confirmed” to the recorded time/place and omits the requested thanks. |
| Prompt-only workshop/context | Uses the recorded time/place and omits thanks. Its opening says it can confirm details. |
| Prompt-only export/context and personalized | “I saw” adds a completed action. “Now in JSONL format” turns a file-selection correction into a statement about the export's state. |
| Prompt-only ticket/generic | Calls the update good without evidence and asks to verify details instead of asking which test to run. |
| Prompt-only ticket/context | Repeats the supported branch information but asks whether the recipient ran tests instead of which test the owner should run. |
| Prompt-only ticket/personalized | Says the update already uses the branch, although the source instructs the owner to use it. It also asks whether tests were run. |

The prompt-only workshop/generic output invented a 10 AM start, September 5 date,
Room 101 and a `workshop_schedule` evidence key. Citation validation rejected it.
The prompt-only export/generic output cited `current_message` as evidence for
having seen the correction. The task field is outside the factual evidence
list, so citation validation rejected that response too.

The generic ticket response passed structural checks with unsupported evaluative
wording labeled social. This illustrates the need to inspect every segment,
including questions and greetings.

## Reproduce and continue

Use a verified local daemon with the installed model. Replace the endpoint and
digest placeholders, choose a fresh receipt, and run from the repository root.

```sh
PYTHONPATH=src python3 -m personal_context.format_comparison \
  examples/reply_intent_development/manifest.json NEW_RECEIPT.json \
  --local-model qwen2.5:7b --expected-model-digest EXACT_DIGEST \
  --model-endpoint http://127.0.0.1:PORT --confirm-local-only \
  --model-timeout 60 --model-max-tokens 512 --model-seed 29
```

Repeat that command with `--output NEW_REPORT.json` to run its declared pair.

The transport seam preserves the production request format and failure handling.
The diagnostic exercises the optional transport constraint separately. Regression
tests check identical prompts/options, incomplete/tool response rejection,
strict parsing, literal source validation and development-only inputs.

All 159 tests passed on Python 3.14.3 and 3.11.0. The 20-case retrieval regression
passed with zero boundary violations, and all 13 scripted generation cases
passed. Source-label validation, memory/draft/CLI demos, JavaScript syntax and
whitespace checks also passed. GitHub Actions status is checked after push.

Next isolate the union-schema behavior on these development cases, then measure
supported, on-task replies under a separate frozen evaluation. Current results
cover one quantized model and three authored situations, with the constrained
arm run first. Broader generalization, order effects and human preference need
additional evaluation.

Interview explanation — “I isolated the decoder constraint while keeping prompts
and evidence identical. Refusals dropped, but citation checks caught fabricated
sources and inspection exposed unsupported claims. That gives me a concrete
next experiment for improving reply quality.”
