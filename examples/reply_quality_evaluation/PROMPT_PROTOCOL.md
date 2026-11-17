# Fixed prompt comparison

Compare the v4 prompt with v5, which asks the model to check each requested
action and preserve the certainty, timing, and conditions of cited facts. Use
the same review packet and reply schema in both arms. Send each prompt without
a transport schema. Both arms use the strict JSON parser, literal citation
checks, and the existing requirement for human review. The earlier decoder
diagnostic supplied the choice to use prompt-only decoding.

Use the installed local Qwen2.5 7B model with digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
on cloud-disabled Ollama 0.40.13. Set temperature to zero, seed to 29,
output limit to 512 tokens, and timeout to 60 seconds. Use lexical retrieval
with window-1 thread expansion. Run v4 first on each split. Keep the prompt,
retrieval and model settings fixed through both runs.

Use generic, context and personalized modes. The three development cases
give nine attempts per arm. The six held-out cases give 18 attempts per arm,
including two expected no-history skips. Declare both inputs before starting
inference. The receipt binds the exact messages, cases, task criteria, code,
prompt texts, model and settings. Check that prepared packet fingerprints,
retrieved sources and call decisions match across prompt arms.

Use the existing task criteria and support labels. Count supported and complete
replies out of all attempts as the primary measure. Report draft counts,
rejections, refusals, no-history skips, support and task completion separately.
Export masked reviewer packets with coordinator seed 29. Record reviewer
provenance, score once before inspecting the arm assignments, and retain
individual ratings as well as decoded counts.

```sh
PYTHONPATH=src python3 -m personal_context.prompt_comparison declare \
  examples/reply_quality_evaluation/manifest.json \
  examples/reply_quality_evaluation/criteria.json NEW_DECLARATION.json \
  --split evaluation --local-model qwen2.5:7b --expected-model-digest EXACT_DIGEST \
  --model-endpoint http://127.0.0.1:PORT --confirm-local-only \
  --model-timeout 60 --model-max-tokens 512 --model-seed 29
```

Repeat with `run` and `--output NEW_RESULTS.json` after saving both
declarations. Use the same command with the development directory and
`--split development` for the development run. Export and score the results
with the existing review CLI. The holdout is synthetic and the fixed arm
order leaves possible order effects. User preferences need separate evidence.
[Review instructions](../reply_intent_development/REVIEW.md)
