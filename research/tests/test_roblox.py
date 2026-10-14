import json
import unittest

from bayesguard.model import Policy
from bayesguard.roblox import Detector, EMISSIONS, KINDS, STATES, TRANSITIONS, make_sessions
from bayesguard.roblox_viewer import MILESTONES, render_roblox_viewer


class RobloxTests(unittest.TestCase):
    def test_probabilities_and_filter(self):
        self.assertTrue(all(abs(sum(row) - 1) < 1e-9 for row in TRANSITIONS))
        self.assertTrue(all(abs(sum(row) - 1) < 1e-9 for row in EMISSIONS))
        detector = Detector(Policy(.5, 2))
        for kind in KINDS:
            risk, alert = detector.update(kind)
            self.assertGreaterEqual(risk, 0)
            self.assertLessEqual(risk, 1)
            self.assertEqual(len(detector.posterior), len(STATES))
            self.assertIsInstance(alert, bool)

    def test_deterministic_sessions_and_ground_truth(self):
        sessions = make_sessions(8, 42)
        self.assertEqual(sessions, make_sessions(8, 42))
        self.assertIsNone(sessions[0].attack_start)
        self.assertIsNotNone(sessions[1].attack_start)
        self.assertEqual({s.scenario for s in sessions},
                         {"benign", "movement", "remote", "automation"})

    def test_viewer_separates_sources_and_simulation(self):
        html = render_roblox_viewer(sessions=4)
        self.assertIn("What this tool actually does", html)
        self.assertIn("Documented milestones", html)
        self.assertIn("Simulated server telemetry", html)
        for _, _, _, url in MILESTONES:
            self.assertIn(url, html)
        raw = html.split('<script id="bg-data" type="application/json">', 1)[1].split(
            "</script>", 1)[0]
        data = json.loads(raw)
        self.assertEqual(len(data["scenarios"]), 4)
        self.assertEqual(data["phase_label"], "cheat")
        self.assertEqual(len(data["scenarios"][0]["events"][0]["posterior"]), 4)


if __name__ == "__main__":
    unittest.main()
