"""Check the compiled Zig -> Rust path against Python inference."""

from pathlib import Path
import subprocess
import unittest

from bayesguard.model import Detector, Policy
from bayesguard.roblox import Detector as RobloxDetector, make_sessions as make_roblox_sessions

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin"


@unittest.skipUnless((BIN / "normalizer.exe").exists() and
                     (BIN / "bayesguard-detector.exe").exists(),
                     "compiled Windows ARM64 binaries are not present")
class NativeParityTests(unittest.TestCase):
    def test_pipeline_matches_python(self):
        source = (ROOT / "sample-events.tsv").read_text(encoding="utf-8")
        normalized = subprocess.run([BIN / "normalizer.exe"], input=source,
                                    text=True, capture_output=True, check=True)
        self.assertEqual(normalized.stdout, source)
        native = subprocess.run([BIN / "bayesguard-detector.exe", ".5", "2"],
                                input=normalized.stdout, text=True,
                                capture_output=True, check=True)
        input_rows = [line.split("\t") for line in source.splitlines()]
        output_rows = [line.split("\t") for line in native.stdout.splitlines()]
        self.assertEqual(len(input_rows), len(output_rows))
        detector = None
        current_session = None
        for (session, step, kind), (out_session, out_step, risk_text, alert_text) in zip(
                input_rows, output_rows):
            if session != current_session:
                detector = Detector(Policy(.5, 2))
                current_session = session
            risk, alert = detector.update(kind)
            self.assertEqual((out_session, out_step), (session, step))
            self.assertAlmostEqual(float(risk_text), risk, places=7)
            self.assertEqual(alert_text, str(int(alert)))

    def test_normalizer_rejects_unknown_event(self):
        result = subprocess.run([BIN / "normalizer.exe"],
                                input="s0000\t0\tunknown\n", text=True,
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_roblox_pipeline_matches_python(self):
        sessions = make_roblox_sessions(8, 42)
        source = "".join(f"{session.session_id}\t{step}\t{kind}\n"
                         for session in sessions
                         for step, kind in enumerate(session.events))
        normalized = subprocess.run([BIN / "normalizer.exe"], input=source,
                                    text=True, capture_output=True, check=True)
        self.assertEqual(normalized.stdout, source)
        native = subprocess.run([BIN / "bayesguard-detector.exe", "--roblox", ".5", "2"],
                                input=source, text=True, capture_output=True, check=True)
        rows = [line.split("\t") for line in native.stdout.splitlines()]
        expected_count = sum(len(session.events) for session in sessions)
        self.assertEqual(len(rows), expected_count)
        index = 0
        for session in sessions:
            detector = RobloxDetector(Policy(.5, 2))
            for step, kind in enumerate(session.events):
                risk, alert = detector.update(kind)
                sid, out_step, native_risk, native_alert = rows[index]
                self.assertEqual((sid, out_step), (session.session_id, str(step)))
                self.assertAlmostEqual(float(native_risk), risk, places=7)
                self.assertEqual(native_alert, str(int(alert)))
                index += 1


if __name__ == "__main__":
    unittest.main()
