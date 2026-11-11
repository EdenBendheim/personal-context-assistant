# Decoder constraint diagnostic

Run on the three existing development cases with explicit reply tasks. Compare
the Ollama request with its JSON schema in the `format` field against one with
that field omitted. The JSON schema stays in the prompt in both arms. Use the
same installed Qwen2.5 7B digest, v4 prompt, lexical window-1 retrieval, seed 29,
temperature zero, 512-token cap and 60-second timeout. Each arm includes the
same three modes and up to nine model calls. Verify prompt hashes and retrieved
source IDs match across arms.

Commit this protocol and runner before obtaining results. Use a verified
cloud-disabled local daemon and write a declaration before inference.
`python3 -m personal_context.format_comparison MANIFEST RECEIPT` declares the
comparison. Run the same command with `--output NEW_REPORT` and the same
local model flags to execute it. Keep raw responses in ignored local storage.

Both arms run the same strict proposal parser and citation checks. Keep
rejections and abstention reasons in the report. Review any drafts for factual
support and whether they respond to the task. This diagnostic can show whether
omitting `format` changes refusals or parser errors on these cases. It cannot
establish reply quality or which part of the prompt drives the behavior. Keep
the production schema constraint and human review requirement. Use a separate
study for held-out cases.
