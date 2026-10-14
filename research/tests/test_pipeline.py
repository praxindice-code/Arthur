"""The user-facing page must come from the native pipeline, not a parallel demo."""

import json
from pathlib import Path
import unittest

from bayesguard.model import Policy
from bayesguard.pipeline import _parse_frames, run_pipeline
from bayesguard.roblox import Detector

BIN = Path(__file__).resolve().parents[1] / "bin"
ROOT = Path(__file__).resolve().parents[1]


def embedded_data(html: str) -> dict:
    raw = html.split('<script id="bg-data" type="application/json">', 1)[1].split(
        "</script>", 1)[0]
    return json.loads(raw)


@unittest.skipUnless((BIN / "normalizer.exe").exists() and
                     (BIN / "bayesguard-detector.exe").exists(),
                     "native binaries are not present")
class PipelineTests(unittest.TestCase):
    def test_synthetic_round_trip_and_python_parity(self):
        output = ROOT / "tests" / "_pipeline-synthetic-viewer.html"
        try:
            summary = run_pipeline(output, sessions=4, seed=42)
            data = embedded_data(output.read_text(encoding="utf-8"))
        finally:
            self.assertTrue(output.resolve().is_relative_to(ROOT.resolve()))
            output.unlink(missing_ok=True)
        self.assertEqual(summary.source, "synthetic")
        self.assertEqual(summary.session_count, 4)
        self.assertEqual(data["data_origin"], "synthetic")
        self.assertEqual(data["scenarios"][0]["label"], "benign")
        self.assertEqual(data["scenarios"][1]["label"], "cheat")
        for scenario in data["scenarios"]:
            detector = Detector(Policy(.5, 2))
            for event in scenario["events"]:
                risk, _ = detector.update(event["kind"])
                self.assertAlmostEqual(event["risk"], risk, places=7)
                for actual, expected in zip(event["posterior"], detector.posterior):
                    self.assertAlmostEqual(actual, expected, places=7)

    def test_imported_sessions_are_unlabeled_and_anonymized(self):
        source = ROOT / "tests" / "roblox-input-fixture.tsv"
        output = ROOT / "tests" / "_pipeline-imported-viewer.html"
        try:
            summary = run_pipeline(output, input_path=source)
            html = output.read_text(encoding="utf-8")
            data = embedded_data(html)
        finally:
            self.assertTrue(output.resolve().is_relative_to(ROOT.resolve()))
            output.unlink(missing_ok=True)
        self.assertEqual(summary.source, "imported")
        self.assertEqual(data["scenarios"][0]["label"], "unlabeled")
        self.assertEqual(data["scenarios"][0]["id"], "session-001")
        self.assertNotIn("secret-player-id", html)
        self.assertIn("ground truth is unknown", html)


class FrameTests(unittest.TestCase):
    def test_rejects_reopened_session(self):
        with self.assertRaisesRegex(ValueError, "reappears"):
            _parse_frames("a\t0\tmove_ok\nb\t0\tmove_ok\na\t0\tmove_ok\n")

    def test_rejects_gaps(self):
        with self.assertRaisesRegex(ValueError, "consecutive"):
            _parse_frames("a\t0\tmove_ok\na\t2\tmove_ok\n")


if __name__ == "__main__":
    unittest.main()
