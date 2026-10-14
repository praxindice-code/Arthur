"""Source-linked Roblox defensive timeline plus offline simulated detector view."""

from html import escape
import json
from pathlib import Path

from .model import Policy
from .roblox import Detector, STATES, make_sessions

MILESTONES = (
    ("2023-10-27", "Exploit-prevention partnership",
     "Roblox announced a security partnership with Synapse Softworks and described enforcement against cheating and exploiting.",
     "https://devforum.roblox.com/t/exploit-prevention-update/2663101"),
    ("2024-06-25", "Ban API and alternate-account detection",
     "Roblox introduced creator-facing experience bans and alternate-account detection.",
     "https://devforum.roblox.com/t/introducing-the-ban-api-and-alt-account-detection/3039740/1"),
    ("2025-01-08", "Account farming and automated play",
     "Roblox identified account farming, accelerated play, and modified clients as concerns and described Hyperion, bot detection, and server-authority work.",
     "https://devforum.roblox.com/t/preventing-account-farming-and-exploits/3360580/1"),
    ("2025-05-06", "Automated action on modified clients",
     "Roblox said detected modified clients could trigger account action, including termination.",
     "https://devforum.roblox.com/t/an-update-on-automated-action-against-modified-clients/3640609"),
)

NOTES = {
    "move_ok": "Movement remained within the game's server-side rules.",
    "action_ok": "Action passed server-side validation.",
    "latency_spike": "Network jitter is common and should not prove cheating by itself.",
    "movement_violation": "A server-side movement check observed an impossible or implausible step.",
    "remote_reject": "The server rejected a client-requested action after validation.",
    "reward_mismatch": "A reward or progression request conflicts with server-held state.",
    "repetitive_timing": "Action timing is unusually repetitive; accessibility tools can also produce patterns.",
}
STATE_NAMES = {
    "normal": "Normal", "movement": "Movement abuse",
    "remote_abuse": "Invalid requests", "automation": "Automation",
}


def _timeline_html(data_origin: str, native_pipeline: bool) -> str:
    cards = []
    for date, title, description, url in MILESTONES:
        cards.append(
            f'<article class="milestone"><time datetime="{escape(date)}">{escape(date)}</time>'
            f'<h3>{escape(title)}</h3><p>{escape(description)}</p>'
            f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Roblox source ↗</a></article>'
        )
    source_explanation = (
        'invented server-side gameplay events. No player or Roblox account is connected.'
        if data_origin == "synthetic" else
        'events from a local file. Session names are anonymized in this page; no Roblox service is contacted.'
    )
    section_heading = "Simulated server telemetry" if data_origin == "synthetic" else "Imported server telemetry"
    section_caption = (
        'Select a scenario, then press Play. The shaded region marks synthetic cheat behavior; '
        'the risk curve is the model’s estimate, not a Roblox measurement.'
        if data_origin == "synthetic" else
        'Select a session, then press Play. Imported sessions have no verified cheat labels. '
        'An alert is a model signal, not proof of cheating.'
    )
    engine_explanation = (
        'Zig checks the event rows, then Rust updates a hand-configured sequential model.'
        if native_pipeline else
        'Python updates a hand-configured sequential model in this standalone preview.'
    )
    return (
        '<section class="guide" aria-labelledby="guide-title">'
        '<h2 id="guide-title">What this tool actually does</h2>'
        '<div class="guide-grid">'
        '<p><strong>1 · Read the record</strong><br>Browse dated Roblox announcements below. These are sourced facts, not model inputs.</p>'
        f'<p><strong>2 · Play a scenario</strong><br>Step through {source_explanation}</p>'
        f'<p><strong>3 · Watch the estimate</strong><br>{engine_explanation} Its percentage is not calibrated for real players.</p>'
        '<p><strong>4 · Change the alert rule</strong><br>The slider and consecutive-event setting change when an alert appears. Bayesian tuning is optional future work, not part of this run.</p>'
        '</div><p class="guide-warning">This is a research demo, not a live anti-cheat, breach detector, or evidence for banning someone.</p>'
        '</section>'
        '<section class="history" aria-labelledby="history-title">'
        '<div class="section-heading"><h2 id="history-title">Documented milestones</h2>'
        '<span class="history-tag">Public Roblox statements · not an exhaustive cheat chronology</span></div>'
        '<div class="timeline">' + "".join(cards) + '</div>'
        '<p class="history-note">Roblox has not published a complete, dated inventory of cheat development. '
        'The categories below are a defensive simulation based on Roblox creator guidance, '
        'not claims that these exact incidents occurred on the dates above. '
        '<a href="https://create.roblox.com/docs/scripting/security/security-tactics" target="_blank" rel="noopener noreferrer">Security guidance ↗</a> · '
        '<a href="https://create.roblox.com/docs/scripting/security/client-server-boundary" target="_blank" rel="noopener noreferrer">Server validation ↗</a></p>'
        '</section>'
        f'<section class="simulation-heading"><h2>{section_heading}</h2>'
        f'<p>{section_caption}</p></section>'
    )


def render_roblox_viewer(*, seed: int = 42, sessions: int = 12,
                         threshold: float = .5, streak: int = 2,
                         prepared_scenarios: list[dict] | None = None,
                         data_origin: str = "synthetic") -> str:
    if not .25 <= threshold <= .95 or streak not in (1, 2, 3, 4):
        raise ValueError("use threshold 0.25-0.95 and streak 1-4")
    if data_origin not in ("synthetic", "imported"):
        raise ValueError("invalid data origin")
    if prepared_scenarios is None:
        if sessions < 4:
            raise ValueError("use at least four sessions")
        scenarios = []
        for session in make_sessions(sessions, seed):
            detector = Detector(Policy(threshold, streak))
            events = []
            for kind in session.events:
                risk, _ = detector.update(kind)
                events.append({"kind": kind, "risk": round(risk, 8),
                               "posterior": [round(p, 8) for p in detector.posterior]})
            scenarios.append({"id": session.session_id, "attack_start": session.attack_start,
                              "label": "benign" if session.attack_start is None else "cheat",
                              "events": events})
    else:
        scenarios = prepared_scenarios
        if not scenarios or any(not row.get("events") for row in scenarios):
            raise ValueError("viewer needs nonempty sessions")
    data = {"seed": seed, "threshold": threshold, "streak": streak,
            "states": STATES, "scenarios": scenarios, "notes": NOTES,
            "state_names": STATE_NAMES, "phase_label": "cheat",
            "event_fallback": "Server-side gameplay signal", "data_origin": data_origin}
    assets = Path(__file__).parent
    html = (assets / "viewer-template.html").read_text(encoding="utf-8")
    css = (assets / "viewer.css").read_text(encoding="utf-8")
    js = (assets / "viewer.js").read_text(encoding="utf-8")
    extra_css = (assets / "roblox-viewer.css").read_text(encoding="utf-8")
    html = html.replace("ArthurAI · Attack sequence explorer", "ArthurAI · Roblox cheat evolution")
    html = html.replace("Watch an audit session turn suspicious", "Explore Roblox cheat defense over time")
    html = html.replace("Each event changes the model’s estimate of attack activity. Step through a simulated session and adjust when an alert fires.",
                        "A sourced timeline of Roblox’s anti-cheat response, paired with a hands-on model of server-side gameplay signals.")
    html = html.replace('    <section class="controls"',
                        _timeline_html(data_origin, prepared_scenarios is not None)
                        + '\n    <section class="controls"')
    html = html.replace("Attack risk", "Model score")
    html = html.replace("Offline demonstration using simulated cloud events and hand-set model probabilities. This view does not represent a production detection system.",
                        "Offline defensive prototype. Model probabilities are hand-set and uncalibrated. Do not sanction players from its output.")
    html = html.replace("/* BAYESGUARD_CSS */", css + "\n" + extra_css)
    html = html.replace("/* BAYESGUARD_JS */", js)
    html = html.replace("/* BAYESGUARD_DATA */", json.dumps(data, separators=(",", ":")).replace("<", "\\u003c"))
    return html


def create_roblox_viewer(output: Path, **kwargs) -> Path:
    output.write_text(render_roblox_viewer(**kwargs), encoding="utf-8")
    return output
