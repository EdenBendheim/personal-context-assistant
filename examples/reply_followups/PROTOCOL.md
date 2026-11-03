# Followup evidence stress set

Twelve invented situations, six development and six evaluation contacts. This is
a targeted regression/stress set, not 50 diverse real-user examples or a blind
sample. All 24 source records, required-source annotations and cases are fixed
before inference. The November 1 eight-case study is unchanged and remains prior
development evidence; this set is a separate experiment.

Cases exercise followups that omit a topic word, explicit corrections/negation,
an unavailable lexical seed, a detail over 24 hours away, separate source/thread
boundaries, equal timestamps, another contact and an exclusive-cutoff distractor.
Required sources identify the minimum information needed for the reference fact.
Extra sources are not exhaustively labeled; do not interpret source recall as
retrieval precision, entailment or reply usefulness. Missing-seed and distant/
separate-thread situations intentionally remain difficult for bounded expansion.

## Declared comparison

- Keep query, result limit 5, contacts, cutoffs, messages, prompt v3, seed 29,
  temperature 0, context 8192 and 512 output tokens unchanged.
- Compare lexical retrieval (window 0) with neighbor window **1**, within **24
  hours**, maximum **128** eligible messages. The policy comes from the prior
  equipment omission; do not select a window from these evaluation outcomes.
- Audit required-source coverage on development, then evaluation with the same
  policy. Generic mode intentionally has no evidence and is reported separately.
- Use local Qwen2.5 **7B** for the paired generation comparison, exact digest
  recorded after local installation/file verification. Qwen2.5 1.5B may be run
  on development with neighbor evidence as an additional diagnostic, not a
  controlled evaluation-model comparison. The larger model was chosen for a
  bounded instruction-following check, not on these evaluation results.
- Run both 7B development variants, freeze source/study/annotation/model/config
  receipts, then run both evaluation variants once. Keep rejections, abstentions
  and actual selected source IDs. Do not repair generated text or change the
  schema/settings after evaluation. Record failed requests, not fake successes.
- Inspect outputs against their actual packets and reference sources; no
  automatic semantic/style score or blind human preference result is available.
  Better coverage does not establish better replies. No sending or real-user data.

Use `personal_context.evidence_coverage` for no-inference coverage and
`personal_context.live_generation` for bounded actual provider attempts. A CLI
exit of 1 retains a failed coverage/rejection report; setup errors exit 2.
Runtime/model files and logs stay ignored locally. Only invented fixture/output
and integrity receipts may be published.
