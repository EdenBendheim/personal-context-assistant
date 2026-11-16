# Held-out synthetic reply cases

Six invented conversations cover a corrected room, a print specification, a
shipment question, a watering condition, a sharing restriction and a missing
drop-off location. Every case has an incoming message, a requested reply goal
and explicit task criteria. The fixture includes an update exactly at the
cutoff, a later message, and another contact's message.

The manifest and message fingerprint is
`4ea54fc149b915ccce4c46fbf138bab73083deb06262a3703bbfbf99b12512e9`.
The canonical task criteria fingerprint is
`474161e5b46931817fbfa117e8256ca433081d106725d7fb157dcd4d99ed2653`.
Use these hashes to verify the evaluation inputs before a declared model run.
The fixtures use separate contact scopes from the earlier development and
evaluation examples. Keep them out of prompt and retrieval tuning.

Choose and record the model identity, prompt, decoding, retrieval settings and
review procedure using development cases before running this set. Then use
`personal_context.live_generation` with `--split evaluation` to record all
generic, context and personalized attempts. Export each study or matched set
using the same support and task rubric. Context and personalized modes may
skip a response when evidence is unavailable. Preserve those skips in the
denominator.

A scripted provider verified fixture loading, scoring boundaries and the
18-attempt study path. Real model inference and independent ratings on these
cases are pending. [Review rubric and CLI](../reply_intent_development/REVIEW.md)
