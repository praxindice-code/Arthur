# ArthurAI

ArthurAI is a **review-only Roblox anti-cheat research pilot**. It collects bounded, anonymous server-side summaries and analyzes labeled sessions offline. It does not kick, ban, block gameplay, or send data to a hosted service.

## What runs today

- `roblox/ArthurAIUniversal.server.lua`: opt-in, server-side 10-second movement and RemoteEvent-count summaries. It prints `ARTHURAI_PILOT_V3` rows and exposes a server-only `ArthurAIWindow` event.
- `roblox/ArthurAIEvents.lua`: optional hooks for outcomes and movement contexts that the **game server has already verified**. Never forward a client's claim directly into a hook.
- `arthur/analyze.py`: validates V1–V3 logs, learns separate normal movement limits per game/context, scores windows with a fixed HMM, and evaluates review policies on labeled sessions. Bayesian optimization searches the alert threshold/streak **offline**; it does not tune game physics or deploy bans.
- `arthur/movement_ctbn.py`: a tested, movement-only continuous-time model for *timed* traces. The V3 collector emits window maxima, so it cannot yet feed this model. This experiment is not running in Roblox.

No Rust or Zig component is in this repo: the existing native demos are not connected to this Roblox pilot. Python 3.10+ is the only local requirement.

## Run locally

```powershell
python -m unittest discover -s tests -q
python -m arthur.analyze examples/pilot-output.log
```

The example log is invented V2 data, not a player record. For a labeled run, make a CSV with exactly these columns:

```csv
game_id,session_id,label,attack_start_window
123,normal-session,normal,
123,controlled-test,controlled_attack,2
```

Session IDs must match the log. The research evaluator needs at least five reviewed normal and five controlled-test sessions **per game**; this small minimum only exercises the software, not production accuracy.

```powershell
python -m arthur.analyze path\to\studio-output.log --labels path\to\labels.csv --trials 16 --output path\to\new-results.json
```

The output path must not already exist. The model score is not a calibrated probability of cheating, and candidate policies are never deployed automatically.

## Private Studio pilot

1. In an experience you own or are authorized to edit, put `ArthurAIUniversal.server.lua` in a normal **Script** under `ServerScriptService`. Optionally put `ArthurAIEvents.lua` beside it as a **ModuleScript**.
2. Add the Boolean Script attribute `ArthurAIPilotEnabled = true` only when you are ready to run a consented private test.
3. Run a local Studio server. Copy only `ARTHURAI_PILOT_V3` lines from Output for offline analysis. Do not share the entire Output, which can contain unrelated player data.
4. Keep independently reviewed normal sessions separate from controlled tests; do not label a session “cheating” because its score is high.

The collector omits names, Roblox UserIds, chat, remote arguments, and exact position paths from its rows. It caps output at 2,000 windows per server and is **not** a durable telemetry pipeline for a populated live game. Roblox client-owned physics can affect observed movement; a high speed alone is not proof of cheating.

Next engineering step: add a bounded, server-timestamped movement timeline with gap censoring, then validate it in Studio before connecting it to the CTBN. Live ingestion, retention/deletion, reviewer tooling, and measured false-positive rates remain unbuilt.
