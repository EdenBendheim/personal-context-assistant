# A prompt for completing reply tasks

On six held-out synthetic conversations, v5 produced seven supported,
complete replies out of 18 attempts. V4 produced three. Both prompts used
the same local model and the same evidence packets.

| Held-out result | v4 | v5 |
| --- | ---: | ---: |
| Attempts | 18 | 18 |
| Drafts reaching review | 11 | 14 |
| Rejections | 5 | 2 |
| No-history skips | 2 | 2 |
| Supported drafts | 4 | 11 |
| Task complete | 8 | 9 |
| Supported and complete | 3 | 7 |

V5 gained five passing attempts and lost one. It improved both contextual
shipment replies and the personalized plant reply. The generic donation
reply asked for a drop-off location without inventing one. The personalized
printing reply lost a passing result. Both v5 rejections contained invalid
proposal JSON. Three v5 drafts reaching review still exceeded their evidence,
including rehearsal replies that added a commitment. The 24 distinct
wordings were rated from a masked packet before unblinding by the same
assistant that wrote the prompt and prepared the study. Human ratings,
order effects, and performance with other models or real conversations
remain open.
[Held-out attempts](reply-prompts-2026-11-16/evaluation-results.json) ·
[Held-out ratings](reply-prompts-2026-11-16/evaluation-ratings.json) ·
[Held-out scores](reply-prompts-2026-11-16/evaluation-scores.json)


The comparison asks whether the v5 prompt helps a model finish the requested
actions while keeping claims supported. The protocol was committed in
`5177ef404b48ade4f752b59b19a52bfdc6b264d0` before inference. Both arms used
the same installed Qwen2.5 7B model, lexical retrieval with window-1 thread
expansion, seed, and decoding settings. Both prompts supplied the same reply
schema. They used prompt-only decoding with the same parser and literal
citation checks. Both declarations bind the complete normalized inputs,
criteria, prompt text, source code, and model settings. The paired reports
verify the same draft packet hashes, retrieved sources, and model-call
decisions for every case.
[Protocol](../examples/reply_quality_evaluation/PROMPT_PROTOCOL.md) ·
[Model receipt](reply-prompts-2026-11-16/model-identity.json)

On three development conversations, both prompts produced seven drafts from
nine attempts. The v4 wording completed zero tasks. The v5 wording completed
four tasks and two of those drafts also had factual support. One v5 draft
acknowledged the JSONL correction and asked where to find the file. Another
named the intended branch and asked which tests the owner should run. The
development reviewer had seen earlier v4 outputs. The rating rubric treats
claims about completed actions, such as having seen or noted a correction,
as requiring evidence.
[Development attempts](reply-prompts-2026-11-16/development-results.json) ·
[Development ratings](reply-prompts-2026-11-16/development-ratings.json) ·
[Development scores](reply-prompts-2026-11-16/development-scores.json)

The study made 50 actual requests on a cloud-disabled loopback Ollama daemon.
Both splits included every original attempt and the held-out split had four
no-history skips across both prompts. The audit verified all calls, matching
packet hashes and installed model blobs. The temporary daemon stopped after
the run. Both score files reproduce through the review CLI. All 170 local
tests passed on Python 3.11 and 3.14, along with the 20 retrieval and 13
scripted drafting cases and other smoke checks.

For interviews, “I compared two prompts on identical evidence and scored
both factual support and task completion. The revised prompt passed both
checks in seven of 18 held-out attempts, versus three for the baseline.”
