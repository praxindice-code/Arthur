"""Movement CTBN factor: timing, context, and conservative coverage."""

import math
import unittest

from arthur.movement_ctbn import Segment, band_speed, fit_normal


def trace(*items):
    return tuple(Segment(*item) for item in items)


class TestMovementCTBN(unittest.TestCase):
    def test_bands_use_each_games_normal_limit(self):
        self.assertEqual(band_speed(0.2, 20), "idle")
        self.assertEqual(band_speed(80, 100), "ordinary")
        self.assertEqual(band_speed(80, 20), "fast")
        with self.assertRaises(ValueError):
            band_speed(float("nan"), 20)

    def test_long_fast_grounded_motion_is_less_likely_than_normal_motion(self):
        normal = trace(("grounded", "ordinary", 60),
                       ("grounded", "fast", 2),
                       ("grounded", "ordinary", 60))
        model = fit_normal("123", {f"normal-{i}": normal for i in range(3)})
        unusual = trace(("grounded", "ordinary", 30),
                        ("grounded", "fast", 62),
                        ("grounded", "ordinary", 30))
        self.assertEqual(model.support["grounded"]["sessions"], 3)
        self.assertEqual(model.score(normal).modeled_seconds, 122)
        self.assertLess(model.score(unusual).log_likelihood,
                        model.score(normal).log_likelihood)

    def test_fast_ragdoll_has_different_game_specific_rates(self):
        normal = trace(("grounded", "ordinary", 60),
                       ("grounded", "fast", 2),
                       ("grounded", "ordinary", 60),
                       ("ragdoll", "fast", 20))
        model = fit_normal("123", {f"normal-{i}": normal for i in range(3)})
        ragdoll = trace(("ragdoll", "fast", 20))
        grounded = trace(("grounded", "fast", 20))
        self.assertGreater(model.score(ragdoll).log_likelihood,
                           model.score(grounded).log_likelihood)
        self.assertNotEqual(model.rates["grounded"]["fast"],
                            model.rates["ragdoll"]["fast"])

    def test_sparse_vehicle_context_abstains(self):
        normal = trace(("grounded", "ordinary", 30))
        model = fit_normal("123", {"a": normal, "b": normal})
        vehicle = model.score(trace(("vehicle", "fast", 40)))
        self.assertIsNone(vehicle.log_likelihood)
        self.assertEqual(vehicle.modeled_seconds, 0)
        self.assertEqual(vehicle.unmodeled_seconds, 40)
        self.assertNotIn("vehicle", model.rates)

    def test_invalid_timing_and_unmerged_runs_are_rejected(self):
        normal = trace(("grounded", "ordinary", 30))
        model = fit_normal("123", {"a": normal, "b": normal})
        for value in (0, -1, float("nan"), float("inf"), 3601, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                model.score(trace(("grounded", "ordinary", value)))
        with self.assertRaises(ValueError):
            model.score(trace(("grounded", "ordinary", 2),
                              ("grounded", "ordinary", 3)))
        with self.assertRaises(ValueError):
            fit_normal("invalid", {"a": normal})

    def test_context_change_is_not_mistaken_for_movement_transition(self):
        normal = trace(("grounded", "ordinary", 30),
                       ("ragdoll", "fast", 30))
        model = fit_normal("123", {"a": normal, "b": normal})
        self.assertTrue(math.isfinite(model.score(normal).log_likelihood))
        self.assertEqual(model.score(normal).modeled_seconds, 60)
        self.assertEqual(model.score(normal).unmodeled_seconds, 0)


if __name__ == "__main__":
    unittest.main()
