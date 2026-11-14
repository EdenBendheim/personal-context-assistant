# Union, flat schema and prompt-only decoding

The flat schema produced one draft for review in nine requests, the same
count as the union schema. Two requests that abstained under the union
returned mixed reply and abstention fields under the flat schema. The
validator rejected both.

| Decoder setting | Drafts for review | Abstentions | Rejections |
|---|---:|---:|---:|
| Union schema | 1 | 8 | 0 |
| Flat schema | 1 | 6 | 2 |
| Prompt only | 7 | 0 | 2 |

The [protocol](../examples/reply_intent_development/UNION_PROTOCOL.md) was
committed in `e0964c99b399be1fe8d59f65907ea5a0afa91f00` before inference.
All 27 requests used Qwen2.5 7B on a cloud-disabled local Ollama 0.40.13
daemon. Each arm used the same nine packets, v4 prompt messages, source
lists, settings and model files. The flat arm changed the transport schema
while the prompt continued to describe the union. The declaration binds
the normalized requests and messages as well as the original fixture
files. Raw responses stayed in the ignored run directory, and the daemon
was stopped after inference.
[Declaration](reply-union-2026-11-13/declaration.json) ·
[Model receipt](reply-union-2026-11-13/model-identity.json) ·
[Results](reply-union-2026-11-13/results.json)

Both constrained arms produced the same workshop draft. It cites the
correct time and room, adds the stronger wording “confirmed,” and omits
the requested thanks. The two mixed flat-schema responses ask where to
find the second export file and claim the owner saw the correction, a
claim the source does not establish. Their nonempty abstention reasons
made them invalid replies.

The prompt-only arm reproduced the November 10 pattern. A fabricated
workshop citation and an attempt to cite the incoming task as evidence
were rejected. The seven drafts reaching review still include unsupported
completion claims, misplaced assurance, or questions that miss part of
the reply goal. “Draft for review” counts successful structural checks.
Human support and usefulness ratings remain pending.

This run used three authored development situations, one model, and one
fixed arm order. Removing the top-level union did not raise the reviewable
draft count under these conditions. Future comparisons should measure
whether a draft fulfills the requested task and whether its claims are
supported, using a frozen rubric and independent cases before adopting
a decoding change.

For interviews, “I kept prompts and sources fixed while changing the JSON
decoder constraint. A flatter schema turned two refusals into invalid
replies, so I kept the validator as the gate and separated reply count
from reply quality.”
