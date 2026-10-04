"""Fixed, synthetic retrieval evaluation; no reply generator or external service."""

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .messages import Message, read_jsonl, utc_timestamp
from .store import Store


def reference(message: Message | dict) -> tuple[str, str]:
    if isinstance(message, Message):
        return message.source, message.id
    return message["source"], message["id"]


def eligible(message: Message | dict, case: dict, *, style: bool = False) -> bool:
    fields = vars(message) if isinstance(message, Message) else message
    owner, contact = case["owner"].casefold(), case["contact"].casefold()
    pair = (fields["author"], fields["recipient"])
    return (pair == (owner, contact) or (not style and pair == (contact, owner))) and (
        utc_timestamp(fields["timestamp"]) < utc_timestamp(case["before"]))


@dataclass(frozen=True)
class Benchmark:
    messages: tuple[Message, ...]
    cases: tuple[dict, ...]
    fingerprint: str


def load_benchmark(path: str | Path) -> Benchmark:
    path = Path(path)
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("version") != 1:
        raise ValueError("Unsupported benchmark version")
    fixture = path.parent / manifest["messages"]
    messages = tuple(read_jsonl(fixture))
    by_ref = {reference(message): message for message in messages}
    if not messages or len(by_ref) != len(messages) or len({m.fingerprint for m in messages}) != len(messages):
        raise ValueError("Benchmark messages must be nonempty and unique")
    partitions = manifest["partitions"]
    if set(partitions) != {"development", "evaluation"}:
        raise ValueError("Declare development and evaluation thread partitions")
    thread_split = {}
    for split, threads in partitions.items():
        if not threads or len(set(threads)) != len(threads):
            raise ValueError("Thread partitions must be nonempty and unique")
        for thread in threads:
            if thread in thread_split:
                raise ValueError("A conversation cannot enter multiple partitions")
            thread_split[thread] = split
    if set(thread_split) != {message.thread for message in messages}:
        raise ValueError("Partitions must account for every fixture conversation")
    cases = manifest["cases"]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Cases must be nonempty with unique IDs")
    for case in cases:
        if case["split"] not in partitions or thread_split.get(case["thread"]) != case["split"]:
            raise ValueError("Case conversation is outside its declared partition")
        if not isinstance(case["query"], str) or not case["query"].strip():
            raise ValueError("Cases require a nonempty retrieval query")
        if type(case["limit"]) is not int or case["limit"] < 1:
            raise ValueError("Case limits must be positive integers")
        if case["owner"].casefold() == case["contact"].casefold():
            raise ValueError("Owner and contact must differ")
        utc_timestamp(case["before"])
        pair = {case["owner"].casefold(), case["contact"].casefold()}
        if not any(m.thread == case["thread"] and {m.author, m.recipient} == pair for m in messages):
            raise ValueError("Case conversation must belong to its declared participants")
        for field in ("relevant", "style_relevant", "forbidden"):
            refs = [reference(raw) for raw in case[field]]
            if len(set(refs)) != len(refs) or any(ref not in by_ref for ref in refs):
                raise ValueError("Case references must be unique, known source/message pairs")
            if field != "forbidden":
                for ref in refs:
                    message = by_ref[ref]
                    if not eligible(message, case, style=field == "style_relevant"):
                        raise ValueError("Expected context cannot contain future, wrong-contact, or incoming style records")
                    if thread_split[message.thread] != case["split"]:
                        raise ValueError("Expected examples cannot cross conversation partitions")
        positive = {reference(raw) for field in ("relevant", "style_relevant") for raw in case[field]}
        if positive & {reference(raw) for raw in case["forbidden"]}:
            raise ValueError("A record cannot be both relevant and forbidden")
    fingerprint = hashlib.sha256(manifest_bytes + b"\0" + fixture.read_bytes()).hexdigest()
    return Benchmark(messages, tuple(cases), fingerprint)


def evaluate(benchmark: Benchmark, *, split: str = "evaluation", store: Store | None = None) -> dict:
    if split not in ("development", "evaluation", "all"):
        raise ValueError("Unknown benchmark split")
    selected = [case for case in benchmark.cases if split == "all" or case["split"] == split]
    if not selected:
        raise ValueError("No cases in selected split")
    own_store = store is None
    store = store or Store()
    try:
        if own_store:
            # Include adversarial future and other-contact records to exercise the boundaries.
            store.ingest(benchmark.messages)
        reports = []
        for case in selected:
            parameters = {key: case[key] for key in ("owner", "contact", "before", "limit")}
            context = store.search(case["query"], **parameters)
            style = store.style_examples(**parameters)
            found = {reference(item) for item in context}
            expected = {reference(item) for item in case["relevant"]}
            expected_style = {reference(item) for item in case["style_relevant"]}
            forbidden = {reference(item) for item in case["forbidden"]}
            style_refs = {reference(item) for item in style}
            violations = sum(not eligible(item, case) or reference(item) in forbidden for item in context)
            violations += sum(not eligible(item, case, style=True) or reference(item) in forbidden for item in style)
            reports.append(dict(
                id=case["id"], split=case["split"],
                recall=len(found & expected) / len(expected) if expected else None,
                precision=len(found & expected) / len(found) if found else (1.0 if not expected else 0.0),
                style_recall=len(style_refs & expected_style) / len(expected_style) if expected_style else None,
                missing=sorted(expected-found), style_missing=sorted(expected_style-style_refs),
                unexpected=sorted(found-expected), boundary_violations=violations,
                retrieved=sorted(found), style_retrieved=sorted(style_refs)))
        recalls = [case["recall"] for case in reports if case["recall"] is not None]
        return dict(version=1, benchmark_sha256=benchmark.fingerprint, split=split, cases=reports,
                    case_count=len(reports),
                    macro_recall=sum(recalls)/len(recalls) if recalls else None,
                    macro_precision=sum(case["precision"] for case in reports)/len(reports),
                    boundary_violations=sum(case["boundary_violations"] for case in reports),
                    passed=all(not case["missing"] and not case["style_missing"] and not case["unexpected"]
                               and not case["boundary_violations"] for case in reports),
                    limitation="Synthetic retrieval regression benchmark; does not evaluate generated replies or real-user quality")
    finally:
        if own_store:
            store.close()


def main():
    parser = argparse.ArgumentParser(description="Run a fixed synthetic retrieval benchmark in memory")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--split", choices=("development", "evaluation", "all"), default="evaluation")
    args = parser.parse_args()
    try:
        report = evaluate(load_benchmark(args.manifest), split=args.split)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
