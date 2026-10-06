"""Movement-only conditional CTBN factor for offline research.

This is a fully observed movement node whose transition rates depend on an
observed, server-verified game context. It is not a cheating classifier, a
production inference service, or a replacement for server rule validation.
It requires ordered, timed movement segments; V3 10-second maxima cannot be
used to reconstruct those segments.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


CONTEXTS = ("grounded", "airborne", "ragdoll", "vehicle")
BANDS = ("idle", "ordinary", "fast")
MIN_CONTEXT_SESSIONS = 2
MIN_CONTEXT_SECONDS = 20.0
MAX_SEGMENT_SECONDS = 3600.0
MAX_SESSION_SECONDS = 4 * 3600.0
RATE_PSEUDOCOUNT = 0.25
RATE_PRIOR_SECONDS = 5.0
START_PSEUDOCOUNT = 0.5


def band_speed(speed: float, game_context_limit: float) -> str:
    """Convert an instantaneous horizontal speed using this game's baseline."""
    if (type(speed) not in (int, float) or not math.isfinite(speed) or
            speed < 0 or speed > 100000 or
            type(game_context_limit) not in (int, float) or
            not math.isfinite(game_context_limit) or game_context_limit < 1):
        raise ValueError("invalid movement speed or context limit")
    if speed < 1:
        return "idle"
    return "ordinary" if speed <= game_context_limit else "fast"


@dataclass(frozen=True)
class Segment:
    context: str
    band: str
    seconds: float


@dataclass(frozen=True)
class MovementScore:
    log_likelihood: float | None
    modeled_seconds: float
    unmodeled_seconds: float
    calibrated_contexts: tuple[str, ...]
    # A likelihood density is not a probability of cheating. Compare only
    # traces measured in the same units and evaluated on untouched data.


@dataclass(frozen=True)
class MovementCTBN:
    game_id: str
    rates: dict[str, dict[str, dict[str, float]]]
    starts: dict[str, dict[str, float]]
    support: dict[str, dict[str, float | int]]

    def score(self, segments: Sequence[Segment]) -> MovementScore:
        validate_trace(segments)
        log_likelihood = 0.0
        modeled = 0.0
        unmodeled = 0.0
        observed_contexts: set[str] = set()
        for index, segment in enumerate(segments):
            context = segment.context
            if context not in self.rates:
                unmodeled += segment.seconds
                continue
            modeled += segment.seconds
            observed_contexts.add(context)
            if index == 0 or segments[index - 1].context != context:
                log_likelihood += math.log(self.starts[context][segment.band])
            outgoing = self.rates[context][segment.band]
            log_likelihood -= sum(outgoing.values()) * segment.seconds
            if index + 1 < len(segments) and segments[index + 1].context == context:
                log_likelihood += math.log(outgoing[segments[index + 1].band])
        return MovementScore(log_likelihood if modeled else None, modeled,
                             unmodeled, tuple(sorted(observed_contexts)))


def validate_trace(segments: Sequence[Segment]) -> None:
    if not segments:
        raise ValueError("movement trace is empty")
    total = 0.0
    previous: Segment | None = None
    for segment in segments:
        if (not isinstance(segment, Segment) or segment.context not in CONTEXTS
                or segment.band not in BANDS or
                type(segment.seconds) not in (int, float) or
                not math.isfinite(segment.seconds) or
                not 0 < segment.seconds <= MAX_SEGMENT_SECONDS):
            raise ValueError("invalid movement segment")
        if (previous is not None and previous.context == segment.context and
                previous.band == segment.band):
            raise ValueError("adjacent identical segments must be merged")
        total += segment.seconds
        previous = segment
    if total > MAX_SESSION_SECONDS:
        raise ValueError("movement trace exceeds session duration limit")


def fit_normal(game_id: str,
               sessions: Mapping[str, Sequence[Segment]]) -> MovementCTBN:
    """Fit from independently reviewed normal sessions of one game only."""
    if (not isinstance(game_id, str) or not game_id.isdecimal() or
            len(game_id) > 20 or not sessions):
        raise ValueError("game ID and normal sessions are required")
    dwell = {context: {band: 0.0 for band in BANDS} for context in CONTEXTS}
    transitions = {context: {band: {target: 0 for target in BANDS
                                   if target != band} for band in BANDS}
                   for context in CONTEXTS}
    starts = {context: {band: 0 for band in BANDS} for context in CONTEXTS}
    context_sessions = {context: set() for context in CONTEXTS}
    for session_id, segments in sessions.items():
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session ID is required")
        validate_trace(segments)
        for index, segment in enumerate(segments):
            context = segment.context
            context_sessions[context].add(session_id)
            dwell[context][segment.band] += segment.seconds
            if index == 0 or segments[index - 1].context != context:
                starts[context][segment.band] += 1
            if index + 1 < len(segments) and segments[index + 1].context == context:
                target = segments[index + 1].band
                transitions[context][segment.band][target] += 1
    fitted_rates: dict[str, dict[str, dict[str, float]]] = {}
    fitted_starts: dict[str, dict[str, float]] = {}
    support: dict[str, dict[str, float | int]] = {}
    for context in CONTEXTS:
        seconds = sum(dwell[context].values())
        n_sessions = len(context_sessions[context])
        if n_sessions < MIN_CONTEXT_SESSIONS or seconds < MIN_CONTEXT_SECONDS:
            continue  # No transfer of a different context's rates.
        fitted_rates[context] = {
            band: {target: (transitions[context][band][target] + RATE_PSEUDOCOUNT) /
                    (dwell[context][band] + RATE_PRIOR_SECONDS)
                   for target in BANDS if target != band}
            for band in BANDS
        }
        start_total = sum(starts[context].values()) + START_PSEUDOCOUNT * len(BANDS)
        fitted_starts[context] = {
            band: (starts[context][band] + START_PSEUDOCOUNT) / start_total
            for band in BANDS
        }
        support[context] = {"sessions": n_sessions, "seconds": seconds}
    return MovementCTBN(game_id, fitted_rates, fitted_starts, support)
