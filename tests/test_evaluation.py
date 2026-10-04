import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_context.evaluation import evaluate, load_benchmark, main


MANIFEST = Path(__file__).resolve().parents[1] / "examples/benchmark/manifest.json"


class EvaluationTests(unittest.TestCase):
    def test_fixed_splits_pass_with_future_and_other_contact_distractors_present(self):
        benchmark = load_benchmark(MANIFEST)
        development = evaluate(benchmark, split="development")
        held_out = evaluate(benchmark)
        self.assertTrue(development["passed"])
        self.assertTrue(held_out["passed"])
        self.assertEqual((development["case_count"], held_out["case_count"]), (6, 14))
        self.assertEqual(held_out["macro_recall"], 1.0)
        self.assertEqual(held_out["boundary_violations"], 0)
        self.assertEqual(held_out, evaluate(benchmark))
        self.assertTrue({case["id"] for case in development["cases"]}.isdisjoint(
            case["id"] for case in held_out["cases"]))
        self.assertNotIn("body", json.dumps(held_out))
        cold = next(case for case in held_out["cases"] if case["id"] == "morgan-no-prior-history")
        self.assertEqual((cold["retrieved"], cold["style_retrieved"]), ([], []))
        incoming = next(case for case in held_out["cases"] if case["id"] == "quinn-no-owner-examples")
        self.assertEqual(incoming["style_retrieved"], [])

    def test_runner_detects_a_deliberately_broken_contact_time_and_style_boundary(self):
        benchmark = load_benchmark(MANIFEST)
        case = next(case for case in benchmark.cases if case["split"] == "evaluation")
        other_contact = next(message for message in benchmark.messages if message.recipient != case["contact"])
        future = next(message for message in benchmark.messages
                      if message.thread == case["thread"] and message.timestamp >= case["before"])
        incoming = next(message for message in benchmark.messages
                        if message.thread == case["thread"] and message.author == case["contact"])
        class BrokenStore:
            def search(self, *args, **kwargs):
                return [vars(other_contact), vars(future)]
            def style_examples(self, **kwargs):
                return [vars(incoming)]
        report = evaluate(benchmark, store=BrokenStore())
        self.assertFalse(report["passed"])
        self.assertGreaterEqual(report["boundary_violations"], 3)
        self.assertTrue(report["cases"][0]["missing"])

    def test_manifest_rejects_partition_overlap_future_labels_and_incoming_style(self):
        original = json.loads(MANIFEST.read_text())
        mutations = []
        overlap = deepcopy(original)
        overlap["partitions"]["evaluation"].append(overlap["partitions"]["development"][0])
        mutations.append(overlap)
        future_label = deepcopy(original)
        future_label["cases"][0]["relevant"] = future_label["cases"][0]["forbidden"][:1]
        mutations.append(future_label)
        incoming_style = deepcopy(original)
        incoming_style["cases"][0]["style_relevant"] = [dict(source="gmail", id="1-2")]
        mutations.append(incoming_style)
        unknown = deepcopy(original)
        unknown["cases"][0]["relevant"] = [dict(source="gmail", id="not-a-message")]
        mutations.append(unknown)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"messages.jsonl").write_bytes((MANIFEST.parent/"messages.jsonl").read_bytes())
            for manifest in mutations:
                path = root/"manifest.json"
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    load_benchmark(path)

    def test_fingerprint_changes_when_labels_or_fixture_change(self):
        expected = load_benchmark(MANIFEST).fingerprint
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root/"messages.jsonl"
            fixture.write_bytes((MANIFEST.parent/"messages.jsonl").read_bytes())
            path = root/"manifest.json"
            path.write_bytes(MANIFEST.read_bytes())
            self.assertEqual(load_benchmark(path).fingerprint, expected)
            fixture.write_text(fixture.read_text().replace("yo alex", "hi alex"))
            self.assertNotEqual(load_benchmark(path).fingerprint, expected)

    def test_cli_uses_memory_only_and_returns_failure_for_a_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch("sys.argv", ["context-eval", str(MANIFEST)]), contextlib.redirect_stdout(output):
                main()
            self.assertTrue(json.loads(output.getvalue())["passed"])
            with patch("sys.argv", ["context-eval", str(MANIFEST)]), \
                 patch("personal_context.evaluation.evaluate", return_value={"passed": False}), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
