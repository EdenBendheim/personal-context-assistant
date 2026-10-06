"""Invented-message walkthrough of draft modes and insufficient-history handling."""

import json
from pathlib import Path

from .drafts import DraftEngine, DraftRequest
from .memory import Memory
from .messages import read_jsonl
from .store import Store


def main():
    store = Store()
    try:
        store.ingest(read_jsonl(Path(__file__).resolve().parents[2]/"examples"/"synthetic.jsonl"))
        pair = dict(owner="owner@example.invalid", contact="alex@example.invalid")
        memory = Memory(store)
        memory.create(**pair, kind="fact", text="The Thursday demo should include retrieval.",
                      sources=[("gmail", "1"), ("gmail", "2")], reason="Reviewed schedule and request",
                      at="2026-09-01T10:05:00Z")
        engine = DraftEngine(store, memory)
        drafts = {mode:engine.draft(DraftRequest(**pair, before="2026-09-04T00:00:00Z", query="demo", mode=mode))
                  for mode in ("generic", "context", "personalized")}
        empty = engine.draft(DraftRequest(pair["owner"], "new-contact@example.invalid", "2026-09-04T00:00:00Z", "demo"))
        assert empty["status"] == "needs_history" and not empty["draft_text"]
        assert not drafts["generic"]["citations"] and not drafts["context"]["packet"]["style_examples"]
        assert any(item["kind"] == "memory" for item in drafts["personalized"]["packet"]["evidence"])
        assert all(item["provenance"].get("id") != "5" for item in drafts["personalized"]["packet"]["evidence"])
        print(json.dumps(dict(drafts=drafts, insufficient_history=empty), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
