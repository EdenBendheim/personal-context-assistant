# Decoder schema comparison — November 13, 2026

Compare three decoder settings on the existing workshop, export and ticket
development cases with explicit reply goals. Use generic, context and
personalized modes, for nine requests per setting. Keep every v4 prompt
message, source list, retrieval option and inference parameter fixed.

Run the union schema first, the flat object schema second, and prompt-only
generation third. The flat object allows both fields to be populated, so
the strict parser and proposal validator still reject a reply paired with an
abstention. Keep the union schema in the prompt in all three arms. Record
counts for abstentions, rejections and drafts reaching review. Inspect those
drafts for unsupported claims and missed reply goals. Every draft still
requires human review.

The fixed fixture SHA-256 is
`beac55f03c903b0e020b2bc4e14be2076f6d650c90815f2af9894e01283b2696`.
Use Qwen2.5 7B with installed digest
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
and Ollama 0.40.13, on a cloud-disabled loopback daemon. Verify local model
files, use a 60-second request timeout, seed 29, temperature zero, a 512-token
output cap, and lexical retrieval with window-1 thread expansion.

Commit this protocol before the requests. Write an exclusive declaration
binding the loaded input and file hashes, package source, decoder schemas and
model settings. Reject drift between arms. Retain raw output locally, publish
the synthetic reports and receipts, and stop the temporary daemon.

```sh
PYTHONPATH=src python3 -m personal_context.format_comparison \
  examples/reply_intent_development/manifest.json NEW_RECEIPT.json \
  --comparison union --local-model qwen2.5:7b --expected-model-digest EXACT_DIGEST \
  --model-endpoint http://127.0.0.1:PORT --confirm-local-only \
  --model-timeout 60 --model-max-tokens 512 --model-seed 29
```

Repeat with `--output NEW_REPORT.json` to execute the declared comparison.
This is a development diagnostic on one model and three authored situations.
An independent set, human support and usefulness ratings, and an arm-order
check are separate work.
