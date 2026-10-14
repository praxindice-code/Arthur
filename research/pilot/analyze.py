"""Import universal Roblox pilot windows and propose per-game review policies.

This is offline research tooling, not an automatic deployment or ban system.
Input labels must come from human-reviewed or controlled sessions.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import random
import re
from statistics import median

from bayesguard.optimize import evaluate, search
from bayesguard.sim import Session


PREFIXES = ("ARTHURAI_PILOT_V1 ", "ARTHURAI_PILOT_V2 ", "ARTHURAI_PILOT_V3 ")
MAX_INPUT_BYTES = 20_000_000
MAX_WINDOWS = 100_000
MOVEMENT_CONTEXTS = ("grounded", "airborne", "ragdoll", "vehicle")
MIN_CONTEXT_SESSIONS = 2
MIN_CONTEXT_WINDOWS = 5

# Pilot-only, hand-set stationary HMM. States are normal, unusual movement,
# unusual remote volume, and server-rejected actions. None proves cheating.
PILOT_TRANSITIONS = (
    (.96, .013, .013, .014),
    (.10, .86, .02, .02),
    (.10, .02, .86, .02),
    (.08, .02, .02, .88),
)
# Observation columns: ordinary, movement, remote volume, both, rejected
# outcome, and no movement sample. Each row sums to one.
PILOT_EMISSIONS = (
    (.72, .08, .08, .04, .03, .05),
    (.10, .58, .05, .20, .02, .05),
    (.10, .05, .58, .20, .02, .05),
    (.10, .05, .05, .10, .65, .05),
)


@dataclass(frozen=True)
class Window:
    game_id: str
    session_id: str
    window: int
    started_at: int
    samples: int
    max_horizontal: float
    max_upward: float
    remote_count: int
    ignored_movement: int
    remote_reject_count: int = 0
    reward_mismatch_count: int = 0
    invalid_hit_count: int = 0
    approved_movement_count: int = 0
    nonfinite_movement_count: int = 0
    movement_contexts: dict[str, dict[str, float | int]] | None = None


@dataclass(frozen=True)
class Label:
    game_id: str
    session_id: str
    kind: str
    attack_start_window: int | None


def load_windows(path: Path) -> dict[tuple[str, str], list[Window]]:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("pilot log is too large for one import")
    return parse_windows(path.read_text(encoding="utf-8-sig").splitlines())


def parse_windows(lines) -> dict[tuple[str, str], list[Window]]:
    groups: dict[tuple[str, str], list[Window]] = {}
    seen: set[tuple[str, str, int]] = set()
    count = 0
    for line_number, line in enumerate(lines, 1):
        prefix = next((candidate for candidate in PREFIXES if candidate in line), None)
        if prefix is None:
            continue  # Studio's timestamp and unrelated Output messages.
        payload = line.split(prefix, 1)[1]
        if len(payload) > 2048:
            raise ValueError(f"line {line_number}: oversized pilot row")
        try:
            raw, end = json.JSONDecoder().raw_decode(payload)
            # Studio appends a source annotation after the printed JSON.
            if payload[end:].strip() and not re.fullmatch(
                    r"\s*-\s*Server\s*-\s*[^{}\n]*", payload[end:]):
                raise ValueError("unexpected text after JSON")
            if not isinstance(raw, dict):
                raise ValueError("pilot row must be an object")
            schema = raw.get("schema")
            if (type(schema) is not int or schema not in (1, 2, 3) or
                    prefix != PREFIXES[schema - 1]):
                raise ValueError("unsupported schema")
            required = list(Window.__dataclass_fields__)[:9 if schema == 1 else
                                                        14 if schema == 2 else 15]
            row = Window(**{name: raw[name] for name in required})
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"line {line_number}: invalid pilot row") from exc
        if (not isinstance(row.game_id, str) or not row.game_id.isdecimal()
                or len(row.game_id) > 20
                or not isinstance(row.session_id, str)
                or not 1 <= len(row.session_id) <= 64
                or not all(c.isalnum() or c == "-" for c in row.session_id)
                or any(type(value) is not int for value in (
                    row.window, row.started_at, row.samples,
                    row.remote_count, row.ignored_movement,
                    row.remote_reject_count, row.reward_mismatch_count,
                    row.invalid_hit_count, row.approved_movement_count,
                    row.nonfinite_movement_count))
                or row.window < 0 or row.started_at < 0
                or not 0 <= row.samples <= 1000
                or not 0 <= row.remote_count <= 10000
                or not 0 <= row.ignored_movement <= row.samples
                or any(not 0 <= value <= 10000 for value in (
                    row.remote_reject_count, row.reward_mismatch_count,
                    row.invalid_hit_count, row.approved_movement_count,
                    row.nonfinite_movement_count))
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or value < 0 or value > 100000
                       for value in (row.max_horizontal, row.max_upward))):
            raise ValueError(f"line {line_number}: out-of-range pilot value")
        if schema == 3:
            contexts = row.movement_contexts
            if not isinstance(contexts, dict) or set(contexts) != set(MOVEMENT_CONTEXTS):
                raise ValueError(f"line {line_number}: invalid movement contexts")
            total_samples = 0
            for context in MOVEMENT_CONTEXTS:
                item = contexts[context]
                if not isinstance(item, dict) or set(item) != {
                        "samples", "max_horizontal", "max_upward"}:
                    raise ValueError(f"line {line_number}: invalid {context} summary")
                samples = item["samples"]
                horizontal = item["max_horizontal"]
                upward = item["max_upward"]
                if (type(samples) is not int or not 0 <= samples <= row.samples or
                        any(type(value) not in (int, float) or
                            not math.isfinite(value) or not 0 <= value <= 100000
                            for value in (horizontal, upward)) or
                        (samples == 0 and (horizontal != 0 or upward != 0))):
                    raise ValueError(f"line {line_number}: invalid {context} metrics")
                total_samples += samples
            if total_samples > row.samples:
                raise ValueError(f"line {line_number}: context samples exceed total")
        identity = (row.game_id, row.session_id, row.window)
        if identity in seen:
            raise ValueError(f"line {line_number}: duplicate window")
        seen.add(identity)
        groups.setdefault(identity[:2], []).append(row)
        count += 1
        if count > MAX_WINDOWS:
            raise ValueError("too many pilot windows")
    if not groups:
        raise ValueError("no ArthurAI pilot windows found")
    for identity, rows in groups.items():
        rows.sort(key=lambda row: row.window)
        if [row.window for row in rows] != list(range(len(rows))):
            raise ValueError(f"non-consecutive windows for {identity}")
        if len({row.started_at for row in rows}) != 1:
            raise ValueError(f"inconsistent session time for {identity}")
    return groups


def load_labels(path: Path, groups: dict[tuple[str, str], list[Window]]) -> dict[tuple[str, str], Label]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return parse_labels(csv.DictReader(source), groups)


def parse_labels(reader, groups: dict[tuple[str, str], list[Window]]) -> dict[tuple[str, str], Label]:
    labels = {}
    required = {"game_id", "session_id", "label", "attack_start_window"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("labels need game_id,session_id,label,attack_start_window")
    for number, row in enumerate(reader, 2):
        identity = (row["game_id"], row["session_id"])
        if identity not in groups or identity in labels:
            raise ValueError(f"label row {number}: unknown or duplicate session")
        kind = row["label"]
        start_text = (row["attack_start_window"] or "").strip()
        if kind == "normal" and not start_text:
            start = None
        elif kind == "controlled_attack" and start_text.isdecimal():
            start = int(start_text)
            if start >= len(groups[identity]):
                raise ValueError(f"label row {number}: attack starts after session")
        else:
            raise ValueError(f"label row {number}: invalid label/start")
        labels[identity] = Label(*identity, kind, start)
    return labels


def robust_limit(values: list[float]) -> float:
    center = median(values)
    deviation = median(abs(value - center) for value in values)
    return max(1.0, center + 6 * max(deviation, 0.1))


def fit_limits(groups: dict[tuple[str, str], list[Window]],
               training_normal: list[tuple[str, str]]) -> dict:
    rows = [row for identity in training_normal for row in groups[identity]]
    if not rows:
        raise ValueError("no normal training windows")
    limits = {
        "horizontal": robust_limit([row.max_horizontal for row in rows]),
        "upward": robust_limit([row.max_upward for row in rows]),
        "remote": robust_limit([row.remote_count for row in rows]),
    }
    # Fit only on reviewed-normal training sessions. Sparse contexts remain
    # uncalibrated; their motion cannot become suspicious through a fallback
    # threshold learned from a different mechanic.
    if any(row.movement_contexts is not None for row in rows):
        contexts = {}
        for context in MOVEMENT_CONTEXTS:
            items = [(identity, row.movement_contexts[context])
                     for identity in training_normal for row in groups[identity]
                     if row.movement_contexts is not None and
                     row.movement_contexts[context]["samples"] > 0]
            if (len(items) >= MIN_CONTEXT_WINDOWS and
                    len({identity for identity, _ in items}) >= MIN_CONTEXT_SESSIONS):
                contexts[context] = {
                    "horizontal": robust_limit([item["max_horizontal"] for _, item in items]),
                    "upward": robust_limit([item["max_upward"] for _, item in items]),
                    "training_windows": len(items),
                    "training_sessions": len({identity for identity, _ in items}),
                }
        limits["contexts"] = contexts
    return limits


def score_session(rows: list[Window], limits: dict) -> tuple[float, ...]:
    posterior = (1.0, 0.0, 0.0, 0.0)
    scores = []
    for row in rows:
        if row.movement_contexts is not None:
            calibrated = limits.get("contexts", {})
            has_scored_movement = any(
                row.movement_contexts[context]["samples"] > 0 and
                context in calibrated for context in MOVEMENT_CONTEXTS)
            movement = any(
                row.movement_contexts[context]["samples"] > 0 and
                context in calibrated and
                (row.movement_contexts[context]["max_horizontal"] >
                 calibrated[context]["horizontal"] or
                 row.movement_contexts[context]["max_upward"] >
                 calibrated[context]["upward"])
                for context in MOVEMENT_CONTEXTS)
        else:
            has_scored_movement = row.samples > 0
            movement = (row.samples > 0 and
                        (row.max_horizontal > limits["horizontal"] or
                         row.max_upward > limits["upward"]))
        remote = row.remote_count > limits["remote"]
        rejected = (row.remote_reject_count + row.reward_mismatch_count +
                    row.invalid_hit_count + row.nonfinite_movement_count) > 0
        observation = (4 if rejected else 3 if movement and remote else
                       1 if movement else 2 if remote else
                       5 if not has_scored_movement else 0)
        predicted = [sum(posterior[i] * PILOT_TRANSITIONS[i][j]
                         for i in range(4)) for j in range(4)]
        weighted = [predicted[j] * PILOT_EMISSIONS[j][observation]
                    for j in range(4)]
        total = sum(weighted)
        posterior = tuple(value / total for value in weighted)
        scores.append(1 - posterior[0])
    return tuple(scores)


def describe_movement(row: Window, limits: dict) -> list[dict] | None:
    """Explain context coverage and threshold crossings, not a cheating verdict."""
    if row.movement_contexts is None:
        return None
    result = []
    for context in MOVEMENT_CONTEXTS:
        sample = row.movement_contexts[context]
        if sample["samples"] == 0:
            continue
        baseline = limits.get("contexts", {}).get(context)
        status = "uncalibrated"
        if baseline is not None:
            status = ("above_baseline" if
                      sample["max_horizontal"] > baseline["horizontal"] or
                      sample["max_upward"] > baseline["upward"] else
                      "within_baseline")
        result.append({
            "context": context,
            "status": status,
            "samples": sample["samples"],
            "max_horizontal": sample["max_horizontal"],
            "max_upward": sample["max_upward"],
            "baseline_horizontal": baseline["horizontal"] if baseline else None,
            "baseline_upward": baseline["upward"] if baseline else None,
        })
    return result


def first_review_window(scores: tuple[float, ...], threshold: float,
                        streak: int) -> int | None:
    high = 0
    for index, risk in enumerate(scores):
        high = high + 1 if risk >= threshold else 0
        if high == streak:
            return index
    return None


def zero_false_alert_upper_bound(normal_sessions: int) -> float | None:
    """One-sided 95% binomial upper bound only when zero alerts were observed."""
    if normal_sessions <= 0:
        return None
    return 1 - .05 ** (1 / normal_sessions)


def split_sessions(identities: list[tuple[str, str]], labels: dict,
                   seed: int) -> tuple[list, list, list]:
    rng = random.Random(seed)
    buckets = {"normal": [], "controlled_attack": []}
    for identity in identities:
        buckets[labels[identity].kind].append(identity)
    if any(len(items) < 5 for items in buckets.values()):
        raise ValueError("need at least five reviewed normal and five controlled-attack sessions per game")
    result = [[], [], []]
    for items in buckets.values():
        items.sort()
        rng.shuffle(items)
        n_train = max(3, int(len(items) * .6))
        n_validation = max(1, int(len(items) * .2))
        if n_train + n_validation >= len(items):
            n_train = len(items) - 2
            n_validation = 1
        for target, part in zip(result, (items[:n_train],
                                         items[n_train:n_train + n_validation],
                                         items[n_train + n_validation:])):
            target.extend(part)
    return result[0], result[1], result[2]


def tune_game(game_id: str, groups: dict, labels: dict, seed: int, trials: int) -> dict:
    identities = [identity for identity in groups if identity[0] == game_id and identity in labels]
    versions = {row.movement_contexts is not None
                for identity in identities for row in groups[identity]}
    if len(versions) > 1:
        raise ValueError("cannot tune a game using a mix of V3 and legacy sessions")
    training, validation, test = split_sessions(identities, labels, seed)
    limits = fit_limits(groups, [identity for identity in training
                                 if labels[identity].kind == "normal"])

    def prepared(identities):
        answer = []
        for identity in identities:
            label = labels[identity]
            scores = score_session(groups[identity], limits)
            session = Session(identity[1], tuple("window" for _ in scores),
                              label.attack_start_window)
            answer.append((session, scores))
        return answer

    train_rows, val_rows, test_rows = map(prepared, (training, validation, test))
    candidate, history = search(train_rows, trials, seed, "bayes")
    val = evaluate(val_rows, candidate)
    final = evaluate(test_rows, candidate)
    # A pilot candidate is never automatically promoted. One false alert on a
    # tiny holdout is already enough to fail this preliminary guardrail.
    review_ready = val.false_positives == 0 and final.false_positives == 0
    normal_holdout = sum(labels[identity].kind == "normal"
                         for identity in validation + test)
    review_items = []
    for split_name, identities in (("validation", validation), ("test", test)):
        for identity in identities:
            scores = score_session(groups[identity], limits)
            step = first_review_window(scores, candidate.threshold, candidate.streak)
            if step is None:
                continue
            row = groups[identity][step]
            review_items.append({
                "session_id": identity[1], "split": split_name,
                "window": step, "risk": round(scores[step], 6),
                "evidence": {
                    "max_horizontal": row.max_horizontal,
                    "max_upward": row.max_upward,
                    "remote_count": row.remote_count,
                    "remote_reject_count": row.remote_reject_count,
                    "reward_mismatch_count": row.reward_mismatch_count,
                    "invalid_hit_count": row.invalid_hit_count,
                    "nonfinite_movement_count": row.nonfinite_movement_count,
                    "movement_contexts": row.movement_contexts,
                    "movement_assessment": describe_movement(row, limits),
                },
            })
    return {
        "game_id": game_id,
        "status": "research_candidate_only" if review_ready else "fails_false_alert_guardrail",
        "policy": asdict(candidate),
        "feature_limits": limits,
        "sessions": {"train": len(training), "validation": len(validation), "test": len(test)},
        "validation": asdict(val),
        "untouched_test": asdict(final),
        "normal_holdout_sessions": normal_holdout,
        "zero_false_alert_95pct_upper_bound": (
            zero_false_alert_upper_bound(normal_holdout) if review_ready else None),
        "review_items": review_items,
        "trials": history,
        "warning": "Small reviewed pilots do not establish a production false-alert rate; no automatic release or ban.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ArthurAI universal pilot importer and per-game BO research")
    parser.add_argument("logs", type=Path, help="Studio/server Output text containing ARTHURAI_PILOT_V1/V2/V3 rows")
    parser.add_argument("--labels", type=Path, help="reviewed labels CSV; omit to validate/count only")
    parser.add_argument("--trials", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, help="optional research results JSON")
    args = parser.parse_args()
    groups = load_windows(args.logs)
    summary = {"windows": sum(map(len, groups.values())), "sessions": len(groups),
               "games": sorted({game for game, _ in groups})}
    if args.labels:
        labels = load_labels(args.labels, groups)
        summary["tuning"] = {}
        for game_id in summary["games"]:
            try:
                summary["tuning"][game_id] = tune_game(game_id, groups, labels, args.seed, args.trials)
            except ValueError as exc:
                summary["tuning"][game_id] = {"status": "insufficient_or_invalid_labels", "reason": str(exc)}
    result = json.dumps(summary, indent=2)
    if args.output:
        if args.output.exists():
            parser.error("refusing to overwrite an existing output")
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
