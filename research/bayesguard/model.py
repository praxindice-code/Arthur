"""Time-homogeneous hidden Markov model and alert policy."""

from dataclasses import dataclass

STATES = ("normal", "recon", "credential", "privilege", "exfil")
KINDS = (
    "login_ok", "list_objects", "read_object", "logout", "list_users",
    "login_fail", "assume_role", "read_secret", "bulk_download",
)
TRANSITIONS = (
    (.985, .015, 0, 0, 0),
    (.12, .76, .12, 0, 0),
    (.05, .05, .78, .12, 0),
    (.03, 0, .05, .82, .10),
    (.03, 0, 0, .02, .95),
)
EMISSIONS = (
    (.27, .22, .28, .12, .04, .03, .02, .015, .005),
    (.05, .12, .03, .01, .60, .14, .02, .02, .01),
    (.03, .02, .01, .01, .10, .58, .15, .08, .02),
    (.02, .04, .03, .01, .05, .05, .45, .30, .05),
    (.01, .04, .15, .01, .02, .02, .03, .12, .60),
)
EVENT_INDEX = {name: i for i, name in enumerate(KINDS)}


@dataclass(frozen=True)
class Policy:
    threshold: float
    streak: int


class Detector:
    def __init__(self, policy: Policy):
        if not 0 < policy.threshold < 1 or policy.streak < 1:
            raise ValueError("threshold must be in (0, 1); streak must be positive")
        self.policy = policy
        self.posterior = [1., 0., 0., 0., 0.]
        self.high_count = 0

    def update(self, kind: str) -> tuple[float, bool]:
        try:
            k = EVENT_INDEX[kind]
        except KeyError as exc:
            raise ValueError(f"unknown event kind: {kind}") from exc
        predicted = [sum(self.posterior[i] * TRANSITIONS[i][j]
                         for i in range(5)) for j in range(5)]
        weighted = [predicted[j] * EMISSIONS[j][k] for j in range(5)]
        total = sum(weighted)
        self.posterior = [value / total for value in weighted]
        risk = 1 - self.posterior[0]
        self.high_count = self.high_count + 1 if risk >= self.policy.threshold else 0
        return risk, self.high_count >= self.policy.streak


def risks(events: tuple[str, ...]) -> tuple[float, ...]:
    detector = Detector(Policy(.5, 1))
    return tuple(detector.update(kind)[0] for kind in events)
