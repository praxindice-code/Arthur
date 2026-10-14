"""Small, dependency-free Gaussian-process Bayesian optimizer."""

from dataclasses import asdict, dataclass
from math import erf, exp, pi, sqrt
import random

from .model import Policy, risks
from .sim import Session

GRID = tuple(Policy(round(i / 100, 2), streak)
             for i in range(25, 96, 5) for streak in range(1, 5))


@dataclass(frozen=True)
class Metrics:
    precision: float
    recall: float
    f1: float
    benign_false_alert_rate: float
    mean_detection_delay: float
    objective: float
    true_positives: int
    false_positives: int
    false_negatives: int


def prepare(sessions: list[Session]) -> list[tuple[Session, tuple[float, ...]]]:
    return [(session, risks(session.events)) for session in sessions]


def evaluate(prepared: list[tuple[Session, tuple[float, ...]]], policy: Policy) -> Metrics:
    tp = fp = fn = benign_fp = benign_count = 0
    delays = []
    for session, values in prepared:
        count = 0
        alerts = []
        for step, risk in enumerate(values):
            count = count + 1 if risk >= policy.threshold else 0
            if count == policy.streak:
                alerts.append(step)
        if session.attack_start is None:
            benign_count += 1
            if alerts:
                fp += 1
                benign_fp += 1
        else:
            if any(step < session.attack_start for step in alerts):
                fp += 1
            valid = [step for step in alerts if step >= session.attack_start]
            if valid:
                tp += 1
                attack_length = len(session.events) - session.attack_start
                delays.append((valid[0] - session.attack_start) / attack_length)
            else:
                fn += 1
                delays.append(1.)
    precision = tp / (tp + fp) if tp + fp else 0.
    recall = tp / (tp + fn) if tp + fn else 0.
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
    false_rate = benign_fp / benign_count if benign_count else 0.
    delay = sum(delays) / len(delays) if delays else 0.
    objective = f1 - .20 * false_rate - .10 * delay
    return Metrics(precision, recall, f1, false_rate, delay, objective, tp, fp, fn)


def _point(policy: Policy) -> tuple[float, float]:
    return ((policy.threshold - .25) / .70, (policy.streak - 1) / 3)


def _kernel(a: Policy, b: Policy) -> float:
    x, y = _point(a), _point(b)
    squared = sum((u - v) ** 2 for u, v in zip(x, y))
    return .25 ** 2 * exp(-squared / (2 * .32 ** 2))


def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    result = [[0.] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            value = matrix[i][j] - sum(result[i][k] * result[j][k] for k in range(j))
            result[i][j] = sqrt(max(value, 1e-12)) if i == j else value / result[j][j]
    return result


def _forward(lower: list[list[float]], vector: list[float]) -> list[float]:
    answer = []
    for i, value in enumerate(vector):
        answer.append((value - sum(lower[i][j] * answer[j] for j in range(i)))
                      / lower[i][i])
    return answer


def _backward(lower: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    answer = [0.] * n
    for i in range(n - 1, -1, -1):
        answer[i] = (vector[i] - sum(lower[j][i] * answer[j]
                                   for j in range(i + 1, n))) / lower[i][i]
    return answer


def _expected_improvement(candidate: Policy, tried: list[Policy], scores: list[float],
                          lower: list[list[float]], alpha: list[float]) -> float:
    prior_mean = sum(scores) / len(scores)
    covariance = [_kernel(candidate, old) for old in tried]
    mean = prior_mean + sum(a * b for a, b in zip(covariance, alpha))
    projection = _forward(lower, covariance)
    variance = max(_kernel(candidate, candidate)
                   - sum(value * value for value in projection), 1e-12)
    sigma = sqrt(variance)
    improvement = mean - max(scores) - .005
    z = improvement / sigma
    cdf = (1 + erf(z / sqrt(2))) / 2
    pdf = exp(-z * z / 2) / sqrt(2 * pi)
    return improvement * cdf + sigma * pdf


def search(prepared: list[tuple[Session, tuple[float, ...]]], trials: int,
           seed: int, method: str = "bayes") -> tuple[Policy, list[dict]]:
    if not 1 <= trials <= len(GRID):
        raise ValueError(f"trials must be between 1 and {len(GRID)}")
    if method not in ("bayes", "random"):
        raise ValueError("method must be bayes or random")
    rng = random.Random(seed)
    tried: list[Policy] = []
    scores: list[float] = []
    history = []
    for _ in range(trials):
        remaining = [policy for policy in GRID if policy not in tried]
        if method == "random" or len(tried) < 4:
            candidate = rng.choice(remaining)
        else:
            matrix = [[_kernel(a, b) + (1e-6 if i == j else 0.)
                       for j, b in enumerate(tried)] for i, a in enumerate(tried)]
            lower = _cholesky(matrix)
            prior_mean = sum(scores) / len(scores)
            centered = [score - prior_mean for score in scores]
            alpha = _backward(lower, _forward(lower, centered))
            candidate = max(remaining, key=lambda p: _expected_improvement(
                p, tried, scores, lower, alpha))
        score = evaluate(prepared, candidate).objective
        tried.append(candidate)
        scores.append(score)
        history.append({**asdict(candidate), "training_objective": score})
    winner = max(range(len(scores)), key=scores.__getitem__)
    return tried[winner], history
