import unittest

from bayesguard.model import Detector, Policy, risks
from bayesguard.optimize import evaluate, prepare, search
from bayesguard.sim import make_sessions


class BayesGuardTests(unittest.TestCase):
    def test_posterior_stays_normalized(self):
        detector = Detector(Policy(.7, 2))
        for event in ("login_ok", "list_users", "login_fail", "assume_role", "read_secret"):
            risk, _ = detector.update(event)
            self.assertTrue(0 <= risk <= 1)
            self.assertAlmostEqual(sum(detector.posterior), 1.)

    def test_attack_sequence_increases_risk(self):
        values = risks(("login_ok", "read_object", "list_users", "list_users",
                        "login_fail", "assume_role", "read_secret", "bulk_download"))
        self.assertGreater(max(values[-4:]), values[0])

    def test_tuning_uses_valid_policy_and_holdout(self):
        training = prepare(make_sessions(20, 42))
        holdout = prepare(make_sessions(20, 10042))
        policy, history = search(training, 6, 123)
        self.assertEqual(len(history), 6)
        self.assertEqual(len({(x["threshold"], x["streak"]) for x in history}), 6)
        self.assertTrue(0 <= evaluate(holdout, policy).recall <= 1)


if __name__ == "__main__":
    unittest.main()
