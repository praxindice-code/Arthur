"""Generate an offline, self-contained interactive event viewer."""

import json
from pathlib import Path

from .model import Detector, Policy, STATES
from .sim import make_sessions


def render_viewer(*, seed: int = 42, sessions: int = 10,
                  threshold: float = .5, streak: int = 2) -> str:
    if sessions < 2:
        raise ValueError("viewer needs at least two sessions")
    if not .25 <= threshold <= .95 or streak not in (1, 2, 3, 4):
        raise ValueError("viewer threshold must be 0.25-0.95 and streak must be 1-4")
    policy = Policy(threshold, streak)
    scenarios = []
    for session in make_sessions(sessions, seed):
        detector = Detector(policy)
        trace = []
        for kind in session.events:
            risk, _ = detector.update(kind)
            trace.append({
                "kind": kind,
                "risk": round(risk, 8),
                "posterior": [round(value, 8) for value in detector.posterior],
            })
        scenarios.append({
            "id": session.session_id,
            "attack_start": session.attack_start,
            "events": trace,
        })
    payload = {
        "seed": seed,
        "threshold": threshold,
        "streak": streak,
        "states": STATES,
        "scenarios": scenarios,
    }
    assets = Path(__file__).parent
    template = (assets / "viewer-template.html").read_text(encoding="utf-8")
    css = (assets / "viewer.css").read_text(encoding="utf-8")
    javascript = (assets / "viewer.js").read_text(encoding="utf-8")
    data = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    return (template.replace("/* BAYESGUARD_CSS */", css)
            .replace("/* BAYESGUARD_DATA */", data)
            .replace("/* BAYESGUARD_JS */", javascript))


def create_viewer(output: Path, *, seed: int = 42, sessions: int = 10,
                  threshold: float = .5, streak: int = 2) -> Path:
    html = render_viewer(seed=seed, sessions=sessions,
                         threshold=threshold, streak=streak)
    output.write_text(html, encoding="utf-8")
    return output
