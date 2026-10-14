"""Deterministic synthetic sessions. No production telemetry is used."""

from dataclasses import dataclass
import random

KINDS = (
    "login_ok", "list_objects", "read_object", "logout", "list_users",
    "login_fail", "assume_role", "read_secret", "bulk_download",
)
NORMAL_WEIGHTS = (27, 22, 28, 12, 4, 3, 2, 1.5, .5)


@dataclass(frozen=True)
class Session:
    session_id: str
    events: tuple[str, ...]
    attack_start: int | None


def make_sessions(count: int, seed: int) -> list[Session]:
    rng = random.Random(seed)
    sessions = []
    for i in range(count):
        is_attack = i % 2 == 1
        prefix_size = rng.randint(6, 16)
        events = rng.choices(KINDS, weights=NORMAL_WEIGHTS, k=prefix_size)
        start = len(events) if is_attack else None
        if is_attack:
            # Some intrusions are noisy; others mix normal reads with sparse clues.
            if rng.random() < .35:
                events.extend(rng.choices(
                    ("list_objects", "read_object", "list_users", "login_fail",
                     "assume_role", "read_secret", "bulk_download"),
                    weights=(25, 25, 16, 12, 8, 8, 6), k=rng.randint(7, 13)))
            else:
                events.extend(rng.choices(("list_users", "list_objects", "login_fail"),
                                          weights=(6, 2, 2), k=rng.randint(2, 4)))
                events.extend(rng.choices(("login_fail", "assume_role", "read_secret"),
                                          weights=(5, 3, 2), k=rng.randint(2, 4)))
                events.extend(rng.choices(("assume_role", "read_secret", "bulk_download"),
                                          weights=(2, 4, 4), k=rng.randint(2, 4)))
        else:
            events.extend(rng.choices(KINDS, weights=NORMAL_WEIGHTS,
                                      k=rng.randint(6, 12)))
            if rng.random() < .25:
                # Legitimate administration and backups share some attack events.
                activity = ("list_users", "assume_role", "read_secret") if rng.random() < .6 \
                    else ("list_objects", "read_object", "bulk_download")
                insert_at = rng.randrange(3, len(events))
                events[insert_at:insert_at] = list(activity)
        sessions.append(Session(f"s{i:04d}", tuple(events), start))
    return sessions
