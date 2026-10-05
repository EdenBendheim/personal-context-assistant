"""Synthetic create/correct/withdraw walkthrough; leaves no database on disk."""

import json
from pathlib import Path

from .memory import Memory
from .messages import read_jsonl
from .store import Store


def main():
    store = Store()
    try:
        fixture = Path(__file__).resolve().parents[2]/"examples"/"synthetic.jsonl"
        store.ingest(read_jsonl(fixture))
        memory = Memory(store)
        pair = dict(owner="owner@example.invalid", contact="alex@example.invalid")
        item = memory.create(**pair, kind="fact", text="The demo is planned for Thursday.",
                             sources=[("gmail", "1")], reason="Owner reviewed the schedule", at="2026-09-01T10:00:00Z")
        item = memory.revise(item["memory_id"], expected_revision=1,
                             text="The Thursday demo should include the retrieval example.",
                             sources=[("gmail", "1"), ("gmail", "2")], reason="Alex requested the retrieval example",
                             at="2026-09-01T10:05:00Z")
        before = "2026-09-04T00:00:00Z"
        corrected = memory.context(**pair, before=before)
        assert corrected == [item]
        assert not memory.context(owner=pair["owner"], contact="riley@example.invalid", before=before)
        memory.revoke(item["memory_id"], expected_revision=2, reason="Owner withdrew this memory",
                      at="2026-09-04T12:00:00Z")
        assert not memory.context(**pair, before=before)
        print(json.dumps(dict(corrected_context=corrected, audit_revisions=len(memory.history(item["memory_id"])),
                              withdrawn_context=memory.context(**pair, before=before)), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
