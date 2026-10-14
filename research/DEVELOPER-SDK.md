# ArthurAI developer SDK: first working slice

This is a **local reference implementation**, not a production Roblox service.
It has a server-side Luau adapter, a Rust HTTP ingestion/scoring process, and
a Zig feature-window function linked into that Rust process. The same Rust
sequential model is used by the offline CLI and the live process. Alerts are
review-only and scores are uncalibrated.

## Try the complete local path

From this folder, open two PowerShell terminals. Choose your own random
16+-character key; the value below is only a local example. First terminal:

```powershell
$env:BAYESGUARD_KEY = 'local-demo-key-change-me'
.\bin\bayesguard-live.exe
```

Second terminal:

```powershell
$env:BAYESGUARD_KEY = 'local-demo-key-change-me'
py replay-live.py
Invoke-WebRequest http://127.0.0.1:8787/v1/alerts -Headers @{'x-api-key'=$env:BAYESGUARD_KEY}
```

`replay-live.py` sends `roblox-events.tsv` in batches. The response has one
line per event: `session_id`, `step`, `model_score`, `review_alert`. The alerts
endpoint adds four counts from Zig over the last 32 events: movement,
rejected-remote, reward, and repetitive-timing observations. Replay of the
same event is idempotent; a conflicting replay or step gap is rejected.
The Zig counts explain recent evidence; they do not currently alter the HMM
score. A service restart loses in-memory state and begins a new scoring window
at the next received step.

The preserved `build-native.ps1` is specific to the original Windows ARM64
workspace and must not be run unchanged on another PC. See [BUILD.md](BUILD.md)
for a portable baseline build. The original script compiles Zig's `window.zig`
as an object and links it into Rust's live process; Zig is not a subprocess
in that path. `cargo test --features zig-window` also requires the Zig object
as a linker argument.

## Install in a Roblox experience

1. Put `roblox-sdk/BayesGuard.lua` and `roblox-sdk/Example.server.lua` in
   `ServerScriptService`, not a replicated container. The example is a
   starting point, not a complete anti-cheat for an arbitrary game.
2. Enable **Allow HTTP Requests** in Experience Settings > Security.
3. Put a unique `BayesGuardKey` in the experience's Secrets Store. Do not put
   it in a client-visible script or a committed config file.
4. Replace the example URL with a developer-controlled **HTTPS** endpoint.
   A published Roblox game cannot call the local `127.0.0.1` process on your
   computer. The included Rust process deliberately binds only to loopback;
   it requires an authenticated, rate-limited HTTPS gateway and durable
   storage before public deployment.
5. Call `guard:record(player, kind)` from your own **server-side** validation
   code. A tycoon might emit `reward_mismatch` after rejecting an impossible
   reward claim. An obby might emit `movement_violation` after checking a
   checkpoint transition with its own teleport/boost exceptions. A shooter
   needs weapon- and lag-aware server checks. Never let a client choose an
   event kind as proof of cheating.

The module batches up to 50 events per request, retries failed batches, caps
its queue, and never blocks a game action on a scoring response. The sample
callback only reports a review signal. It never kicks or bans.

## Bayesian optimization: what it would add

The sequential model does the event-by-event scoring. Bayesian optimization
does **not** discover cheaters or replace server validation. The current
educational optimizer searches only threshold and alert streak over a tiny
60-choice grid of synthetic data; an exhaustive sweep would be just as
reasonable. It is not used by the live service.

Later, with labeled and permissioned Roblox sessions, Bayesian optimization
could choose more expensive settings such as feature-window length, HMM
transition/emission priors, per-game thresholds, and the trade-off between
false alerts and detection delay. Each trial must replay held-out player
sessions through the same scorer. We would keep a final untouched test set,
report false flags per 1,000 legitimate sessions, and release tuned settings
as a versioned model. No amount of optimization can compensate for missing
labels or game-specific context.

## Not yet production-ready

The local process keeps sessions and alerts only in memory, handles one
connection at a time, has no persistent reviewer UI, has not been tested in
Roblox Studio, and uses hand-set model probabilities. The Luau module has not
been verified in an actual experience. The hosted HTTPS gateway, per-creator
credentials, data retention/privacy policy, resilience, telemetry schema
versioning, monitoring, and false-positive evaluation remain to be built.
Do not deploy it to real players or use it for enforcement as-is.

Roblox references: [server-authoritative security](https://create.roblox.com/docs/scripting/security/security-tactics),
[HTTP requests](https://create.roblox.com/docs/cloud-services/http-service),
and [secrets](https://create.roblox.com/docs/cloud-services/secrets).
