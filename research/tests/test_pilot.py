"""Edge cases for the universal, review-only ArthurAI pilot importer."""

import csv
import io
import json
from pathlib import Path
import unittest

from pilot.analyze import (Window, describe_movement, first_review_window, fit_limits, load_windows, parse_labels,
                           parse_windows, score_session, tune_game,
                           zero_false_alert_upper_bound)

PILOT = Path(__file__).resolve().parents[1] / "pilot"


def row(session="s-1", window=0, **changes):
    value = {
        "schema": 1, "game_id": "123", "session_id": session,
        "window": window, "started_at": 100, "samples": 0,
        "max_horizontal": 0, "max_upward": 0, "remote_count": 0,
        "ignored_movement": 0,
    }
    value.update(changes)
    return value


def lines(*values, suffix=""):
    return [f"  02:27:14.950  ARTHURAI_PILOT_V{value['schema']} "
            + json.dumps(value) + suffix
            for value in values]


def row_v2(session="s-1", window=0, **changes):
    value = row(session, window, schema=2, remote_reject_count=0,
                reward_mismatch_count=0, invalid_hit_count=0,
                approved_movement_count=0, nonfinite_movement_count=0)
    value.update(changes)
    return value


def row_v3(session="s-1", window=0, context="grounded", speed=10, **changes):
    contexts = {name: {"samples": 0, "max_horizontal": 0, "max_upward": 0}
                for name in ("grounded", "airborne", "ragdoll", "vehicle")}
    contexts[context] = {"samples": 10, "max_horizontal": speed, "max_upward": 0}
    value = row_v2(session, window, schema=3, samples=20,
                   max_horizontal=speed, movement_contexts=contexts)
    value.update(changes)
    return value


def labels_from_text(text, groups):
    return parse_labels(csv.DictReader(io.StringIO(text)), groups)


class TestPilot(unittest.TestCase):
    def test_imports_studio_output_and_zero_sample_window(self):
        groups = parse_windows(lines(row(window=0), row(window=1, samples=10),
                                     suffix="  -  Server - ArthurAIUniversal:60"))
        self.assertEqual([w.samples for w in groups[("123", "s-1")]], [0, 10])

    def test_rejects_duplicate_and_missing_windows(self):
        for values in ((row(), row()), (row(), row(window=2))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_windows(lines(*values))

    def test_rejects_bad_metrics_and_trailing_text(self):
        for value in (row(samples=-1), row(max_upward=float("nan")),
                      row(remote_count=10001), row(ignored_movement=1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_windows(lines(value))
        with self.assertRaises(ValueError):
            parse_windows(lines(row(), suffix=" attacker-controlled-tail"))

    def test_v2_outcomes_are_parsed_and_change_review_risk(self):
        normal = parse_windows(lines(*[row_v2(window=i, samples=20) for i in range(4)]))
        rejected = parse_windows(lines(*[row_v2(window=i, samples=20,
                                                remote_reject_count=1) for i in range(4)]))
        normal_rows = normal[("123", "s-1")]
        rejected_rows = rejected[("123", "s-1")]
        self.assertEqual(rejected_rows[0].remote_reject_count, 1)
        limits = {"horizontal": 100, "upward": 100, "remote": 100}
        self.assertGreater(score_session(rejected_rows, limits)[-1],
                           score_session(normal_rows, limits)[-1])

    def test_v2_rejects_missing_or_bad_outcome_counts(self):
        for value in (row_v2(remote_reject_count=-1),
                      row_v2(invalid_hit_count=10001),
                      row_v2(reward_mismatch_count=True),
                      row_v2(nonfinite_movement_count=-1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_windows(lines(value))
        missing = row_v2()
        del missing["remote_reject_count"]
        with self.assertRaises(ValueError):
            parse_windows(lines(missing))
        wrong_prefix = "ARTHURAI_PILOT_V1 " + json.dumps(row_v2())
        with self.assertRaises(ValueError):
            parse_windows([wrong_prefix])

    def test_v3_context_calibration_distinguishes_launch_like_motion(self):
        values = []
        for session in ("normal-a", "normal-b", "normal-c"):
            for index in range(5):
                values.append(row_v3(session, index, speed=10))
                # Ragdoll legitimately reaches much higher speed in this game.
                values[-1]["movement_contexts"]["ragdoll"] = {
                    "samples": 5, "max_horizontal": 400, "max_upward": 0}
                values[-1]["max_horizontal"] = 400
        for session, context in (("ground-attack", "grounded"),
                                 ("ragdoll-normal", "ragdoll")):
            for index in range(4):
                values.append(row_v3(session, index, context=context, speed=300))
        groups = parse_windows(lines(*values))
        limits = fit_limits(groups, [("123", session) for session in
                                     ("normal-a", "normal-b", "normal-c")])
        self.assertIn("grounded", limits["contexts"])
        self.assertIn("ragdoll", limits["contexts"])
        self.assertGreater(score_session(groups[("123", "ground-attack")], limits)[-1],
                           score_session(groups[("123", "ragdoll-normal")], limits)[-1])
        self.assertEqual(describe_movement(groups[("123", "ground-attack")][0],
                                           limits)[0]["status"], "above_baseline")
        self.assertEqual(describe_movement(groups[("123", "ragdoll-normal")][0],
                                           limits)[0]["status"], "within_baseline")

    def test_v3_sparse_context_abstains_and_bad_contexts_are_rejected(self):
        values = [row_v3(session, index) for session in ("normal-a", "normal-b")
                  for index in range(5)]
        values += [row_v3("unknown-ragdoll", index, context="ragdoll", speed=900)
                   for index in range(3)]
        groups = parse_windows(lines(*values))
        limits = fit_limits(groups, [("123", "normal-a"), ("123", "normal-b")])
        self.assertNotIn("ragdoll", limits["contexts"])
        self.assertLess(score_session(groups[("123", "unknown-ragdoll")], limits)[-1], .5)
        self.assertEqual(describe_movement(groups[("123", "unknown-ragdoll")][0],
                                           limits)[0]["status"], "uncalibrated")
        invalid = row_v3()
        invalid["movement_contexts"]["grounded"]["samples"] = True
        with self.assertRaises(ValueError):
            parse_windows(lines(invalid))

    def test_v3_contexts_flow_through_research_tuning(self):
        values = []
        labels = ["game_id,session_id,label,attack_start_window"]
        for index in range(10):
            session = f"context-{index}"
            attack = index >= 5
            for window in range(5):
                speed = 500 if attack and window >= 2 else 10
                values.append(row_v3(session, window, speed=speed))
            labels.append(f"123,{session}," +
                          ("controlled_attack,2" if attack else "normal,"))
        groups = parse_windows(lines(*values))
        result = tune_game("123", groups,
                           labels_from_text("\n".join(labels), groups), 42, 6)
        self.assertIn("grounded", result["feature_limits"]["contexts"])
        self.assertEqual(result["feature_limits"]["contexts"]["grounded"]
                         ["training_sessions"], 3)
        self.assertIn(result["status"],
                      ("research_candidate_only", "fails_false_alert_guardrail"))

    def test_tuning_rejects_mixed_context_and_legacy_sessions(self):
        values = [row_v3("new", 0), row_v2("old", 0, samples=20)]
        groups = parse_windows(lines(*values))
        labels = labels_from_text(
            "game_id,session_id,label,attack_start_window\n"
            "123,new,normal,\n123,old,normal,\n", groups)
        with self.assertRaisesRegex(ValueError, "mix of V3 and legacy"):
            tune_game("123", groups, labels, 42, 6)
        invalid = row_v3()
        invalid["movement_contexts"]["grounded"]["samples"] = 0
        with self.assertRaises(ValueError):
            parse_windows(lines(invalid))

    def test_approved_movement_is_not_suspicion_and_one_spike_needs_streak(self):
        baseline = parse_windows(lines(row_v2(samples=20)))[("123", "s-1")]
        approved = parse_windows(lines(row_v2(samples=20,
                                              approved_movement_count=1)))[("123", "s-1")]
        limits = {"horizontal": 100, "upward": 100, "remote": 100}
        self.assertEqual(score_session(baseline, limits), score_session(approved, limits))
        self.assertIsNone(first_review_window((.1, .9, .1), .5, 2))

    def test_labels_must_match_sessions_and_attack_window(self):
        groups = parse_windows(lines(row()))
        for identity, start in (("missing", "0"), ("s-1", "1")):
            with self.subTest(identity=identity, start=start), self.assertRaises(ValueError):
                labels_from_text(
                    "game_id,session_id,label,attack_start_window\n"
                    f"123,{identity},controlled_attack,{start}\n", groups)

    def test_game_baselines_are_separate_and_never_auto_deploy(self):
        values = []
        label_rows = ["game_id,session_id,label,attack_start_window"]
        for game_id in ("123", "456"):
            for index in range(10):
                session = f"{game_id}-{index}"
                attack = index >= 5
                for window in range(5):
                    values.append(row(session, window, game_id=game_id,
                                      samples=20,
                                      max_horizontal=(500 if attack and window >= 2 else 10),
                                      remote_count=(100 if attack and window >= 2 else 3)))
                label_rows.append(f"{game_id},{session},"
                                  f"{'controlled_attack,2' if attack else 'normal,'}")
        groups = parse_windows(lines(*values))
        labels = labels_from_text("\n".join(label_rows), groups)
        for game_id in ("123", "456"):
            result = tune_game(game_id, groups, labels, 42, 6)
            self.assertEqual(result["sessions"], {"train": 6, "validation": 2, "test": 2})
            self.assertIn(result["status"], ("research_candidate_only", "fails_false_alert_guardrail"))
            self.assertEqual(result["game_id"], game_id)
            self.assertEqual(result["normal_holdout_sessions"], 2)
            self.assertIsInstance(result["review_items"], list)

    def test_three_thousand_sessions_and_false_alert_bound(self):
        groups = parse_windows(lines(*(row_v2(session=f"p-{i}", samples=20)
                                      for i in range(3000))))
        self.assertEqual(len(groups), 3000)
        self.assertAlmostEqual(zero_false_alert_upper_bound(3000), .0009981, places=6)
        self.assertIsNone(zero_false_alert_upper_bound(0))

    def test_v2_example_and_v3_server_source_contract(self):
        groups = load_windows(PILOT / "example-output.log")
        self.assertEqual(sum(len(rows) for rows in groups.values()), 4)
        collector = (PILOT / "ArthurAIUniversal.server.lua").read_text(encoding="utf-8")
        hooks = (PILOT / "ArthurAIEvents.lua").read_text(encoding="utf-8")
        self.assertIn("ARTHURAI_PILOT_V3", collector)
        self.assertIn('windowEvent.Name = "ArthurAIWindow"', collector)
        self.assertIn('script:GetAttribute("ArthurAIPilotEnabled")', collector)
        for field in ("remote_reject_count", "reward_mismatch_count", "invalid_hit_count",
                      "approved_movement_count", "nonfinite_movement_count"):
            self.assertIn(field, collector)
        for category in ("remote_reject", "reward_mismatch", "invalid_hit"):
            self.assertIn(category, hooks)
        self.assertIn("setMovementContext", hooks)
        self.assertNotIn("ArthurAIIgnoreMovementUntil", collector)
        self.assertNotIn("humanoid:GetState()", collector)
        self.assertNotIn("humanoid.Sit", collector)
        self.assertNotIn(":Kick(", collector)
        self.assertNotIn(":BanAsync(", collector)
        self.assertNotIn("RequestAsync(", collector)

    def test_stationary_hmm_uses_sequential_windows(self):
        normal = [row(window=i, samples=20, max_horizontal=10) for i in range(4)]
        burst = [row(window=i, samples=20, max_horizontal=500) for i in range(4)]
        limits = {"horizontal": 100, "upward": 100, "remote": 100}
        def windows(values):
            return [Window(**{k: v for k, v in item.items() if k != "schema"}) for item in values]
        self.assertGreater(score_session(windows(burst), limits)[-1],
                           score_session(windows(normal), limits)[-1])


if __name__ == "__main__":
    unittest.main()
