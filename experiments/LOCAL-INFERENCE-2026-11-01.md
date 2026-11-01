# First real local inference — November 1, 2026

Local inference now runs through both adapters and the review browser. The
embedding model matches the lexical baseline on the established synthetic
benchmark. **The small reply model is not useful enough yet:** it mostly abstains,
and the few returned drafts include repetition, missed information and an
unsupported claim. No style or reply-quality improvement is established.

## Runtime and integrity

This bounded run used an isolated official Ollama **0.40.13** binary, an explicit
loopback port and `OLLAMA_NO_CLOUD=1`; its startup log confirmed cloud disabled.
No account, paid API, cloud compute or private conversation was used. Both the
temporary review server and model daemon were stopped afterward. Downloaded
runtime/model files remain in ignored `runs/`, outside public commits.

The runtime archive SHA-256 is
`bae29252232b9e1358cf5801a7d65a07442af18fb5467cb68c7fc3711f59c511`.
Source: [official release archive](https://github.com/ollama/ollama/releases/download/v0.40.13/ollama-darwin.tgz).
See [Ollama's local-only configuration](https://docs.ollama.com/faq).

| Use | Exact installed model | Inventory manifest SHA-256 |
| --- | --- | --- |
| Chat | `qwen2.5:1.5b`, Q4_K_M | `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b` |
| Embedding | `nomic-embed-text:v1.5` | `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f` |

[Identity/file receipts](local-inference-2026-11-01/identities.json) record runtime,
capabilities, metadata hashes and streamed verification of every installed blob.
This runtime adds a retained registry manifest to its local wrapper: verification
requires that blob's digest to match inventory and the wrapper without that layer
to equal the original parsed manifest. There are six verified chat blobs and five
embedding blobs. These checks establish local file integrity and bracketed daemon
metadata; they are not a signed producer or served-weight attestation.

## Development changes before evaluation

Eight invented reply situations have disjoint development/evaluation contacts,
four per partition, each tested in generic/context/personalized modes. The source
fixture and reference facts were fixed before inference. No evaluation replies
were examined while changing the prompt.

1. `grounded-draft-v1`: ten development provider attempts rejected, two no-history
   skips. Nine mixed a nonempty abstention with a reply; one was rejected as an
   incomplete response. Nothing was silently repaired or saved.
2. One additional development-only diagnostic captured the mixed response. It also
   labeled a date/commitment as social. The existing validator correctly refused
   its contradictory response shape.
3. `v2` clarified the two shapes in prose. All ten provider attempts still rejected.
4. `v3` constrained the supplied JSON schema to separate reply and abstention
   branches and retained Python validation. Ten development calls completed:
   six abstentions, four drafts requiring review, two no-history skips. The schema
   prevents this structural ambiguity; it does not fix semantic errors.

The exact v3 provider settings, prompt/source/fixture hashes and development
report were [frozen before evaluation](local-inference-2026-11-01/reply-freeze.json).
Generation used temperature 0, seed 29, at most 512 output tokens, context 8192,
60-second socket timeout, 6000 prompt bytes and model unload after every request.
No prompt/model/settings changes followed evaluation.

## Reply results and failures

| Partition / mode | Provider attempts | Drafts requiring review | Abstentions | No-history skips | Rejected |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development / generic | 4 | 0 | 4 | 0 | 0 |
| Development / context | 3 | 1 | 2 | 1 | 0 |
| Development / personalized | 3 | 3 | 0 | 1 | 0 |
| Evaluation / generic | 4 | 0 | 4 | 0 | 0 |
| Evaluation / context | 3 | 0 | 3 | 1 | 0 |
| Evaluation / personalized | 3 | 3 | 0 | 1 | 0 |

“Requires review” is a structural status, **not a usable or factually correct
reply**. No human preference or automatic entailment score was assigned.
Median end-to-end provider-attempt latency was 1.13 seconds on development and
1.18 seconds on evaluation, including model load/metadata checks. This tiny local
run is not a throughput benchmark.

Observed failures:

- Development office-hours reply invents unavailability for the week, although
  its evidence gives room 214. It reaches human review because the model calls
  the unsupported assertion social; segment labels are not semantic validation.
- Another development reply repeats the same uncertainty twelve times.
- Evaluation poster/debugging replies say they lack information despite matching
  facts in their packets. A structurally valid reply can still be unhelpful.
- The equipment reply says “I will bring the equipment.” The lexical topic query
  retrieves the owner's vague equipment message but misses the incoming tripod/
  camera distinction. This is a retrieval omission as well as a weak reply; the
  general reference fact is not evidence the model actually saw.
- Generic mode abstains on every situation. The variants therefore do not provide
  a meaningful blind style comparison, and no personalization benefit is claimed.

A real browser made one additional equipment request, saved its draft and showed
the original wording, literal source and provider labels. “Usable after my review”
was disabled while support remained unchecked. No rating or message was sent;
there were zero console warnings/errors. The screenshot is local/ignored.

The daemon recorded **42 chat responses**: 31 development/diagnostic requests,
10 frozen evaluation requests and one browser smoke. All generated wording is
invented test content. [All reports and receipt hashes](local-inference-2026-11-01/run.json)
retain the earlier failures rather than replacing them with final outcomes.

## Embedding retrieval

The unchanged benchmark contains 31 invented messages, six development cases and
14 evaluation cases. Before observing results, the selection protocol declared
thresholds **0.2, 0.4, 0.6, 0.8**: require zero boundary violations, maximize the
harmonic mean of macro precision/recall, then precision, then threshold.

| Development cosine threshold | Macro recall | Macro precision | Boundary violations |
| --- | ---: | ---: | ---: |
| 0.2 | 1.000 | 0.444 | 0 |
| 0.4 | 1.000 | 0.444 | 0 |
| **0.6 selected** | **1.000** | **1.000** | **0** |
| 0.8 | 0.000 | 0.333 | 0 |

The [development receipt](local-inference-2026-11-01/retrieval-freeze.json) locks
provider identity/configuration, threshold, benchmark and Python source hashes.
Evaluation refuses a changed setup before encoding. The receipt is a consistency
check, not protection against someone deliberately rewriting the entire study.

| Frozen evaluation, 14 cases | Macro recall | Macro precision | Boundary violations |
| --- | ---: | ---: | ---: |
| Lexical baseline | 1.000 | 1.000 | 0 |
| Nomic, threshold 0.6 | 1.000 | 1.000 | 0 |

Both retrieve all labeled context/outbound examples with no unexpected records.
**This is a tie, not evidence embeddings improve retrieval.** The established
synthetic labels are small and author-defined, not a fresh real-user holdout.
Raw text has no query/document prefixes, there is no index/cache, histories are
bounded to 128 eligible messages, and outbound style selection remains lexical.
The 37 embedding HTTP responses include all development candidates and evaluation;
empty eligible histories skip inference. Default drafting/UI retrieval stays lexical.

## Reproduce and extend

With the exact models installed and a cloud-disabled local daemon, run
`personal_context.live_generation` on `examples/local_reply/manifest.json`, first
development then evaluation, with the settings above. Run
`personal_context.frozen_retrieval select` then `evaluate` on
`examples/benchmark/manifest.json`, using the Nomic digest. Use a fresh ignored
freeze path; the selector refuses to overwrite an existing decision. Endpoints
are explicit local settings and may need replacing for a new daemon.

All **137 local tests**, the unchanged **20 lexical retrieval cases** and **13
scripted generation contract cases** pass, as do memory/draft demos, JavaScript
syntax and whitespace checks. These checks are separate from measured model
quality. The scripted suite still includes two false wordings that need human
judgment. Public reports contain no weights, vectors, private messages or credentials.

Next: annotate a larger source-complete reply set, distinguish retrieval omissions
from generation failures, compare an appropriately sized local model, and measure
human factual/usefulness judgments before any style-adapter work. Keep the review
gate and expose unsuccessful attempts. No sending integration is planned.
