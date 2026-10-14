"""Defensive, Roblox-inspired server telemetry experiment.

All sessions and probabilities are invented. This module neither connects to
Roblox nor implements client modification or cheat functionality.
"""

from dataclasses import dataclass
import random

from .model import Policy

STATES = ("normal", "movement", "remote_abuse", "automation")
KINDS = (
    "move_ok", "action_ok", "latency_spike", "movement_violation",
    "remote_reject", "reward_mismatch", "repetitive_timing",
)
INDEX = {name: i for i, name in enumerate(KINDS)}
TRANSITIONS = (
    (.975, .010, .008, .007),
    (.080, .870, .030, .020),
    (.070, .020, .890, .020),
    (.060, .020, .020, .900),
)
EMISSIONS = (
    (.34, .36, .12, .05, .05, .04, .04),
    (.08, .09, .08, .48, .12, .05, .10),
    (.07, .08, .05, .11, .45, .18, .06),
    (.08, .10, .04, .06, .12, .10, .50),
)
NORMAL_WEIGHTS = EMISSIONS[0]
CHEAT_WEIGHTS = {
    "movement": (.12, .10, .08, .48, .08, .05, .09),
    "remote": (.10, .09, .05, .09, .44, .19, .04),
    "automation": (.12, .12, .05, .06, .11, .10, .44),
}


@dataclass(frozen=True)
class Session:
    session_id: str
    events: tuple[str, ...]
    attack_start: int | None
    scenario: str


class Detector:
    """Time-homogeneous HMM: same transition and emission tables each step."""

    def __init__(self, policy: Policy):
        if not 0 < policy.threshold < 1 or policy.streak < 1:
            raise ValueError("invalid alert policy")
        self.policy = policy
        self.posterior = [1., 0., 0., 0.]
        self.high_count = 0

    def update(self, kind: str) -> tuple[float, bool]:
        if kind not in INDEX:
            raise ValueError(f"unknown event kind: {kind}")
        k = INDEX[kind]
        predicted = [sum(self.posterior[i] * TRANSITIONS[i][j]
                         for i in range(4)) for j in range(4)]
        weighted = [predicted[j] * EMISSIONS[j][k] for j in range(4)]
        total = sum(weighted)
        self.posterior = [value / total for value in weighted]
        risk = 1 - self.posterior[0]
        self.high_count = self.high_count + 1 if risk >= self.policy.threshold else 0
        return risk, self.high_count >= self.policy.streak


def risks(events: tuple[str, ...]) -> tuple[float, ...]:
    detector = Detector(Policy(.5, 1))
    return tuple(detector.update(kind)[0] for kind in events)


def make_sessions(count: int, seed: int) -> list[Session]:
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    sessions = []
    for i in range(count):
        scenario = ("benign", "movement", "remote", "automation")[i % 4]
        events = rng.choices(KINDS, weights=NORMAL_WEIGHTS, k=rng.randint(6, 10))
        start = None if scenario == "benign" else len(events)
        if scenario == "benign":
            events.extend(rng.choices(KINDS, weights=NORMAL_WEIGHTS, k=10))
            # Normal play can still include occasional anomalous-looking noise.
            if i % 8 == 0:
                events.insert(len(events) // 2, "latency_spike")
        else:
            weights = CHEAT_WEIGHTS[scenario]
            events.extend(rng.choices(KINDS, weights=weights, k=rng.randint(10, 15)))
        sessions.append(Session(f"r{i:04d}-{scenario}", tuple(events), start, scenario))
    return sessions
