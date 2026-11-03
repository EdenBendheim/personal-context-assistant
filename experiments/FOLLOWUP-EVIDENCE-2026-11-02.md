# Followup evidence and local generation — November 2, 2026

Bounded thread expansion now recovers details that lack the reply topic word.
**Better evidence did not produce useful 7B replies in this run:** every actual
7B request abstained. The change is an explicit CLI option; the review browser
and saved-review policy remain unchanged. No reply-quality or style improvement
is claimed.

## What changed

The unchanged November 1 equipment example retrieves the owner's vague equipment
message but misses the incoming tripod/camera distinction. An independent source
audit makes that omission visible without asking an LLM to grade itself. Required
source annotations bind exact study bytes and reject unknown, duplicate, future
or foreign-contact labels. Reports omit message bodies; extra context is not
exhaustively labeled and is not scored as a precision error.

`NeighborSearch` preserves lexical seeds, then adds nearby messages from the same
provider/thread within 24 hours, bounded by the result limit and 128 eligible
records. It never starts from an unmatched conversation or substitutes another
contact. It retains the original seed in provenance and rechecks the retrieval
snapshot. Neighbor scores inherit lexical seed scores; they are not relevance or
factual-confidence estimates. Outbound writing examples remain unchanged.

The draft CLI, coverage audit and live-provider runner accept
`--neighbor-window 1`. Default 0 retains all historical evaluation-packet hashes.
Existing reviews are not migrated. The draft CLI can initialize memory tables,
as before; it is not read-only.

## Fixed comparison

The new [followup stress set and protocol](../examples/reply_followups/PROTOCOL.md)
contains 12 invented cases, six contacts per partition, and 24 messages. The
fixture, source labels, window 0/1 comparison and 7B model choice were committed
before observing outcomes, at `42e9a3fc48342d4247655ea61a9d32ad01aad895`.
The earlier eight-case study is unchanged and is prior development evidence.

This is an author-written stress set, not a blind real-user sample. Cases cover
corrections, negation, missing topic seeds, distant and separate-thread details,
equal timestamps, another contact, a different provider and a cutoff distractor.
The author knows the labels; the declared evaluation partition is not a claim of
unseen real-world data or a semantic/style benchmark.

The actual-model study used a task-scoped official Ollama 0.40.13 runtime on
loopback. `OLLAMA_NO_CLOUD=1` and its startup log confirmed cloud disabled. Exact
metadata and every local model blob verified for both models:

| Model | Manifest SHA-256 |
| --- | --- |
| Qwen2.5 1.5B | `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b` |
| Qwen2.5 7B, Q4_K_M | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |

The larger public model is from the [official model library](https://ollama.com/library/qwen2.5:7b).
The run reused the previously verified runtime and local cache, downloaded the
4.68 GB 7B model, and stopped the temporary daemon afterward. No private messages,
paid API or cloud compute were used. Model/runtime files remain ignored locally.
[Identity/file receipts](followup-evidence-2026-11-02/identities.json) establish
local file integrity and daemon-reported metadata, not served-weight attestation.

For generation, both retrieval variants used prompt v3, seed 29, temperature 0,
512 output tokens, context 8192, 60-second socket timeout, a 6000-byte prompt
budget and unload after each request. After both 7B development runs, the
[evaluation freeze](followup-evidence-2026-11-02/evaluation-freeze.json) bound
source, protocol, fixture, annotation, model/configuration and development-report
hashes. No prompt/settings change followed evaluation.

## Source coverage

| Corpus / partition | Lexical complete | Window 1 complete |
| --- | ---: | ---: |
| Prior eight-case study, all positive-label contacts | 5/6 | 6/6 |
| New development contacts with required sources | 0/5 | 3/5 |
| New evaluation contacts with required sources | 0/6 | 4/6 |

Context and personalized modes have identical message coverage here; report rows
count them separately (development 0/10 versus 6/10; evaluation 0/12 versus 8/12).
Generic mode intentionally receives no history. The new evaluation macro
required-source recall is **0.000 versus 0.667**. Each positive case has one
required source, so it equals the complete-case fraction in this set.

Recovered evaluation details are the train time/platform, cancellation of
volunteering, book return instructions and staging/production distinction. The
remaining deadline case has no lexical seed, and the rental detail is in another
thread. Development also retains a confirmation more than 24 hours from its
seed. These limits are explicit; expansion does not silently fetch all history
or claim complete semantic retrieval.

## Actual generation outcomes

| Model / partition / retrieval | Mode attempts | Provider calls | Abstentions | Drafts requiring review | No-history skips |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1.5B development, window 1 diagnostic | 18 | 14 | 10 | 4 | 4 |
| 7B development, lexical | 18 | 14 | 14 | 0 | 4 |
| 7B development, window 1 | 18 | 14 | 14 | 0 | 4 |
| 7B evaluation, lexical | 18 | 16 | 16 | 0 | 2 |
| 7B evaluation, window 1 | 18 | 16 | 16 | 0 | 2 |

There were no structural rejections in these runs. That does not make the system
useful: the 7B model returned **no draft** even when the required source was in
its packet. The controlled evaluation therefore demonstrates no reply benefit
from expansion or from a larger model. The 1.5B development-only diagnostic is
not an evaluation-model comparison; its four drafts include vague uncertainty
and new commitments. None was marked usable or sent.

Median provider-attempt times on evaluation were 3.26 seconds lexical and 3.51
seconds with neighbors, including loading and identity checks. These tiny local
runs are not throughput or statistically reliable latency comparisons.

One post-study replay of the **development** workshop case inspected why the 7B
model abstained: it returned “No new information to provide.” Its packet already
had room 12 and the 2 pm start. This diagnostic is not another evaluation run and
caused no prompt/model change. The current request supplies a topic, not a clear
communication intent; that is a candidate design issue to investigate, not a
proven causal explanation. The runner currently retains statuses, errors and
sources but omits most abstention reasons; retaining those is useful next work.

The daemon recorded **75 chat responses**: 14 small-model development calls,
28 paired 7B development calls, 32 paired evaluation calls and one development
diagnostic. [All synthetic outcomes and receipt hashes](followup-evidence-2026-11-02/run.json)
remain inspectable, including non-successes. No model weights, vectors, raw
research data, private messages or credentials are published.

## Checks and next work

All **148 local tests** pass, including 11 new annotation/neighbor/integration
tests. The unchanged **20 lexical retrieval cases**, **13 scripted generation
contract cases**, memory/draft demos, JavaScript syntax and whitespace checks pass.
CI validates the new fixed source labels without running model inference or
inspecting retrieval outcomes. Temporary model service is stopped.

Next, define an explicit reply intent/current-message input and retain abstention
reasons, then evaluate a development-only prompt revision. Use a fresh frozen
evaluation version afterward rather than tuning these outcomes. Add support and
usefulness judgments before changing browser defaults or considering fine-tuning.
Source coverage, safe structure and useful writing are separate requirements.
