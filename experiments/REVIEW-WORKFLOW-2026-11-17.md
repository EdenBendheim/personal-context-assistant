# Local drafting and independent review

The tested v5 prompt is now available through the ordinary draft CLI and review
server. It remains an explicit experimental choice. Existing commands keep v4
with union-schema decoding. The new offline review form lets another reviewer
judge factual support and requested actions without receiving the model labels.

## What ran

Two actual local Qwen2.5 7B requests used v5, prompt-only decoding, seed 29 and a
512-token limit. The CLI and API received the same invented export conversation,
reply goal and lexical query `export JSONL`. Both returned the same packet hash
and this wording.

> I see the correction has been made to use JSONL instead of CSV.
>
> Could you please provide the second file?

The source says, “Correction: use JSONL, not CSV. The second file is the right
one.” The draft asks for the file. Its first sentence still needs review for
whether “has been made” implies a completed file change rather than a correction
to instructions. This smoke check establishes working entry points, persistence
and the review gate. It supplies no new quality score or style-preference result.

The API saved the generated draft and reopened it with current context. Marking
it usable without an explicit support judgment returned HTTP 400. Its original
prompt and decoder settings remained in saved provenance. Sending remained
unavailable. [Observed output and model receipt](review-workflow-2026-11-17/smoke.json)

The daemon used a fresh loopback port and `OLLAMA_NO_CLOUD=1`. Its log confirmed
cloud was disabled. Runtime metadata and every installed model blob verified
against the recorded digest. The temporary daemon and review servers stopped
afterward. A smoke-helper reporting error initially read `status` at the wrong
response level after successful generation. The saved review was reopened and
the gate checked again without further model calls. The receipt records that
recovery. No private messages, paid service or model files were published.

## Try a draft

Start an already installed, cloud-disabled Ollama daemon separately. These
commands do not install a model or change daemon configuration. Use a fresh
local demo database and the correct loopback endpoint for your daemon.

```sh
PYTHONPATH=src python3 -m personal_context.cli --db runs/reply-demo.sqlite \
  import examples/reply_intent_development/messages.jsonl --preview
PYTHONPATH=src python3 -m personal_context.cli --db runs/reply-demo.sqlite \
  import examples/reply_intent_development/messages.jsonl
PYTHONPATH=src python3 -m personal_context.draft_cli \
  --db runs/reply-demo.sqlite --owner owner@example.invalid \
  --contact export@example.invalid --before 2026-09-05T00:00:00Z \
  --query 'export JSONL' --mode personalized \
  --current-message 'Did you see the correction for the export?' \
  --intent 'Acknowledge the correction and ask where to get the second file.' \
  --local-model qwen2.5:7b --confirm-local-only \
  --expected-model-digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e \
  --model-timeout 60 --model-max-tokens 512 --model-seed 29 \
  --draft-prompt grounded-draft-v5 --response-format prompt_only
```

The review server accepts the same model options, with `--db` and `--owner`.
It prints a local authenticated URL. Its launch configuration is fixed for
browser requests. Inspect the original segments and citations, edit the reply
and record your support judgment for that wording revision.

## Collect another review

`reply_quality_cli form` exports standalone HTML from a fixed study, criteria
file and coordinator shuffle seed. The form shows the incoming message, reply
goal, eligible history and anonymous drafts. It collects factual support,
completed actions, notes, reviewer type and prior exposure. Downloaded JSON can
be reopened in the same form after validation. Text is rendered through text
nodes, and embedded data cannot close its JSON script element. A content policy
blocks external resources and network connections.

Use the same inputs and seed for `progress`, `score` and `compare`. `progress`
lists pending judgments without quality scores. `score` requires every draft
and reviewer field, and checks complete attempt coverage. `compare` accepts two
completed files and reports support/action disagreements once per distinct
wording. Agreement does not prove correctness or reviewer independence.

For independent review, the coordinator should keep the study labels and seed
separate from the reviewer. A local form for all 24 distinct held-out wordings
has been prepared with a new coordinator seed. All 24 remain pending. Human
ratings have not been collected. Existing development and evaluation scores
reproduced exactly through the strengthened scorer. The earlier six evaluation
cases remain closed to prompt tuning.

## Verification and limits

All 182 Python tests passed on Python 3.11 and 3.14. All three Node rating-state
tests passed. The 20-case retrieval benchmark passed with zero boundary
violations, all 13 scripted generation cases passed, and the 12 fixed source
annotations validated. Synthetic memory/draft/import demos, JavaScript syntax
and whitespace checks passed.

The browser tool rejected the local-file preview, so visual layout and actual
browser file download/import remain unverified. Python checks cover HTML data
isolation, masking, injection attempts and CLI exports. Node checks cover
rating restoration, mismatched packets and malformed judgments. They do not
replace browser QA. The form has no automatic persistence, and users must
download ratings before closing the tab. The model still needs human review.

For interviews, “I made an experimentally tested prompt usable in the product,
then built a separate review workflow so another person can judge the drafts
against their evidence. The system preserves failures and refuses to score
unfinished reviews.”
