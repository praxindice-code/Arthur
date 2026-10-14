"""One end-to-end offline path: events -> Zig -> Rust -> HTML viewer."""

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .roblox import make_sessions
from .roblox_viewer import render_roblox_viewer

MAX_EVENTS = 10_000  # The generated single-file browser view is intentionally bounded.


@dataclass(frozen=True)
class RunSummary:
    output: Path
    source: str
    session_count: int
    event_count: int
    alert_count: int


def _native(binary: Path, arguments: list[str], source: str) -> str:
    if not binary.is_file():
        raise FileNotFoundError(f"Missing {binary.name}; build the native tools first")
    result = subprocess.run([str(binary), *arguments], input=source, text=True,
                            encoding="utf-8", capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise ValueError(f"{binary.name} failed: {detail}")
    return result.stdout


def _parse_frames(source: str) -> list[tuple[str, int, str]]:
    rows = []
    last_session = None
    last_step = -1
    closed_sessions = set()
    for line_number, line in enumerate(source.splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 3 or not fields[0]:
            raise ValueError(f"line {line_number}: expected session_id, step, event_kind")
        session, step_text, kind = fields
        try:
            step = int(step_text)
        except ValueError as exc:
            raise ValueError(f"line {line_number}: invalid step") from exc
        if session != last_session:
            if session in closed_sessions:
                raise ValueError(f"line {line_number}: session reappears after ending")
            if last_session is not None:
                closed_sessions.add(last_session)
            if step != 0:
                raise ValueError(f"line {line_number}: session must begin at step 0")
            last_session, last_step = session, -1
        if step != last_step + 1:
            raise ValueError(f"line {line_number}: steps must be consecutive")
        rows.append((session, step, kind))
        last_step = step
        if len(rows) > MAX_EVENTS:
            raise ValueError(f"viewer limit is {MAX_EVENTS} events; use a smaller extract")
    if not rows:
        raise ValueError("event input is empty")
    return rows


def run_pipeline(output: Path, *, input_path: Path | None = None,
                 sessions: int = 12, seed: int = 42,
                 threshold: float = .5, streak: int = 2,
                 bin_dir: Path | None = None) -> RunSummary:
    """Run the actual native path and render its scores, without model retraining."""
    if not .25 <= threshold <= .95 or streak not in (1, 2, 3, 4):
        raise ValueError("threshold must be 0.25-0.95 and streak 1-4")
    if input_path is None:
        if sessions < 1:
            raise ValueError("sessions must be positive")
        simulated = make_sessions(sessions, seed)
        raw = "".join(f"{s.session_id}\t{step}\t{kind}\n"
                      for s in simulated for step, kind in enumerate(s.events))
        truths = {s.session_id: s for s in simulated}
        origin = "synthetic"
    else:
        raw = input_path.read_text(encoding="utf-8-sig")
        truths = {}
        origin = "imported"
    _parse_frames(raw)
    native_dir = bin_dir or Path(__file__).resolve().parents[1] / "bin"
    normalized = _native(native_dir / "normalizer.exe", [], raw)
    frames = _parse_frames(normalized)
    if len(frames) != len(raw.splitlines()):
        raise ValueError("normalizer changed the event count")
    scored = _native(native_dir / "bayesguard-detector.exe",
                     ["--roblox", "--posterior", str(threshold), str(streak)], normalized)
    score_rows = [line.split("\t") for line in scored.splitlines()]
    if len(score_rows) != len(frames):
        raise ValueError("detector output count does not match input")

    scenarios = []
    current = None
    seen_alerts = 0
    for (session_id, step, kind), columns in zip(frames, score_rows):
        if len(columns) != 8 or columns[0] != session_id or columns[1] != str(step):
            raise ValueError("detector output is misaligned with input")
        try:
            risk = float(columns[2])
            alert = int(columns[3])
            posterior = [float(value) for value in columns[4:]]
        except ValueError as exc:
            raise ValueError("detector output contains an invalid number") from exc
        if (not 0 <= risk <= 1 or alert not in (0, 1)
                or any(not 0 <= p <= 1 for p in posterior)
                or abs(sum(posterior) - 1) > 1e-6
                or abs(risk - (1 - posterior[0])) > 1e-6):
            raise ValueError("detector output contains invalid probabilities")
        seen_alerts += alert
        if current is None or current["raw_id"] != session_id:
            truth = truths.get(session_id)
            label = "unlabeled" if truth is None else (
                "benign" if truth.attack_start is None else "cheat")
            current = {"raw_id": session_id,
                       "id": session_id if truth else f"session-{len(scenarios) + 1:03d}",
                       "label": label,
                       "attack_start": truth.attack_start if truth else None,
                       "events": []}
            scenarios.append(current)
        current["events"].append({"kind": kind, "risk": risk, "posterior": posterior})
    for scenario in scenarios:
        del scenario["raw_id"]
    html = render_roblox_viewer(seed=seed, threshold=threshold, streak=streak,
                                prepared_scenarios=scenarios, data_origin=origin)
    output.write_text(html, encoding="utf-8")
    return RunSummary(output.resolve(), origin, len(scenarios), len(frames), seen_alerts)
