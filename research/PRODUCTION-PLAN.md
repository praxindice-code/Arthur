# ArthurAI: from study to usable Roblox defense

## Honest status

The current browser page is an offline study with a hand-configured sequential
model. A separate local SDK slice has a Luau module and Rust/Zig ingestion
process; see [DEVELOPER-SDK.md](DEVELOPER-SDK.md). A playable Roblox Studio
[test range](TEST-RANGE.md) now shares one Luau movement detector between
scripted dummies and actual Studio players. That range has not been connected
to the Rust/Zig service. There is still no hosted endpoint, durable review
system, permissioned cross-game player data, or calibrated cheating probability.
Nothing here is evidence for a ban.

## The deployable architecture

```text
Your obby / shooter / tycoon
  Server-side Luau: enforce the game's rules and emit minimal, validated events
                      |
                      v
  Authenticated HTTPS ingest (events are batched; failures never block gameplay)
                      |
                      v
  Rust service: per-session state, sequential scoring, rate limits, audit log,
                alert API, model version, and review queue
           |                                   |
           v                                   v
  Zig library called by Rust                 Database
  via a narrow C ABI: bounded parsing,       Event windows, labels,
  feature windows, compact memory buffers    decisions, retention
           |
           v
  Python offline: backtests, calibration, Bayesian hyperparameter search,
                  model comparison, and signed/versioned model release
                      |
                      v
  Reviewer UI: why a session was flagged, event sequence, false-positive
               feedback, and a human decision. No automatic ban from score.
```

Rust and Zig would be **components of one backend**, not two commands the
developer runs separately. Rust's ownership and concurrency model fit a
long-running, stateful network service. Zig's explicit allocators and C ABI fit
a small, heavily tested high-throughput event/window-processing library. Zig
requires careful bounds and lifetime checks; it is not automatically
memory-safe. Neither language runs inside a Roblox experience. Roblox scripts
are Luau; the native service runs outside Roblox. The server-side boundary,
input validation, access control, and operational security matter more for
resistance to cheating than the implementation language.

## Three games, three signal families

| Experience | Server-authoritative signals to start with | Important legitimate exceptions |
| --- | --- | --- |
| Obby | impossible checkpoint order, movement outside allowed physics, impossible completion time | teleports, boosts, moving platforms, high ping |
| Shooter | shot rate/ammo checks, hit validation, improbable aim or target-switching windows | weapon modifiers, controller aim assist, spectating, lag |
| Tycoon | invalid purchase/reward requests, impossible resource balances, repeated transaction timing | multipliers, refunds, delayed saves, legitimate automation mechanics |

First implement hard server checks that prevent invalid actions. The model is
for ambiguous patterns the hard rules cannot settle. Game-specific features
should be compared within their own game/mode/weapon or progression context;
do not pool the three games into a single undifferentiated threshold.

## What public data can and cannot do

Two downloadable, licensed research datasets can exercise an adapter and
backtest harness:

- [Time-Window Normalized Dataset for Video Game Cheat Detection](https://data.mendeley.com/datasets/bx3y8ktrsf/1): 3,584 labeled two-second windows. Useful for a small, inspectable import and tests. Its features and cheat labels are **not Roblox ground truth**.
- [CS2CD Counter-Strike 2 Cheat Detection](https://huggingface.co/datasets/CS2CD/CS2CD.Counter-Strike_2_Cheat_Detection): about 735 million rows and 52.6 GB, licensed CC BY 4.0 on its dataset card. Useful for scale/performance experiments and perhaps shooter-feature research. Do not download the whole thing merely to run the existing 10,000-event HTML viewer. It is not Roblox data and cannot validate Roblox false-positive rates.

Before trusting either, check its event grain, label provenance, duplicate
sessions, missing fields, time ordering, leakage between training and test
players, and whether its fields can be recreated from **server-side** Roblox
observations. A large row count is not a substitute for representative
players and credible labels. A breach-incident dataset is the wrong grain
altogether: incidents are not per-player gameplay sequences.

Roblox [data stores](https://create.roblox.com/docs/cloud-services/data-stores)
are scoped to a game. There is no general feed of raw player behavior from
unrelated creators' games. Use your own three games, or data voluntarily
shared by another creator with proper permission and a defined data contract.
Cross-game event categories may transfer; raw distributions and thresholds
usually will not.

## Data and training plan

1. Define the event schema: game/version, server session, pseudonymous player
   key, event time, sequence number, action context, server-observed features,
   and a separate reviewed label. Never trust a client-supplied "cheater" flag.
2. Instrument each game and record ordinary play first. Add controlled test
   cases for invalid requests and rule violations; clearly label these as
   scripted tests, not discovered cheaters.
3. Build offline replay that feeds the exact same Rust/Zig scoring core used
   live. Split by **player and time** so nearly identical windows from one
   session cannot leak into both training and test sets.
4. Benchmark a rules-only baseline, then sequential models. Calibrate the
   score and report precision, recall, false flags per 1,000 legitimate
   sessions, and detection delay separately for each game/mode.
5. Use Bayesian optimization only for well-defined choices such as feature
   windows, model hyperparameters, thresholds, and alert streaks. Optimize a
   held-out objective that penalizes false flags. Bayesian optimization is
   **not** a replacement for labels, features, or model validation.
6. Release in shadow mode: collect scores without player-facing action.
   Review alerts, measure drift after game updates, then consider limited
   actions. Keep hard-rule enforcement separate from model suspicion.

## Per-game Bayesian adaptation (proposed, not built)

ArthurAI should have one shared scoring engine and a **separate policy for each
experience and game mode**. An obby's movement limits must not be copied
straight into a shooter or tycoon. The policy would identify a game/mode and
model version, then set a small number of tunable choices: score threshold,
required alert streak, feature-window length, and game-specific exception
handling. Hard server rules (for example, rejecting an impossible purchase)
stay outside the optimizer.

The optimization loop should run **offline in the background**, never in the
gameplay request path:

```text
reviewed, consented sessions for one game/mode
    -> replay through the same scorer used live
    -> Bayesian search proposes a candidate policy
    -> compare with rules-only/current policy on untouched players and later time
    -> approve and version the winner
    -> shadow/canary release, monitor, and roll back if needed
```

Its objective should reward finding confirmed abuse early while imposing a
strict false-alert and reviewer-workload budget on legitimate sessions. Report
these outcomes separately for each game/mode. When a game has little data,
begin with conservative, review-only defaults; related games may inform a
prior **only with the creators' permission**, but their labels and raw player
distribution cannot establish that the new game's policy is safe. Never
auto-tune from unreviewed “suspicious” scores, and do not tune per-player in
real time: that would invite feedback poisoning and unstable decisions.

The existing `roblox-demo` optimizer searches two alert-policy numbers on
synthetic sessions. It does not yet implement this per-game loop, a policy
registry, held-out real-player evaluation, or automatic deployment. A small
Bayesian search can run on a CPU; access to a GPU is not the blocker. The
blocker is authorized, representative, reviewed gameplay data.

There is no honest universal number of training hours or rows. A CPU is enough
for the current HMM, streaming inference, and small Bayesian searches; a GPU
is optional for future large models. Start with hundreds to thousands of
**distinct sessions per game/mode** to test the pipeline and collect many more
for reliable production calibration, especially rare positive examples.
Measure actual runtime once the event rate, window size, and model are fixed.
For perspective, a 1% false-alert rate across 10,000 legitimate sessions means
about 100 false alerts; even 0.1% means about 10. This is why the first output
should be a review queue, not an automatic ban.

## First production milestone

The first usable milestone is **one tycoon in shadow mode**: server-validated
purchase and reward events, authenticated ingestion, real-time per-session
scores, a reviewer view, and replay tests of the same scorer. Transaction
rules have clearer ground truth than ambiguous aim or physics patterns. The
obby and shooter can then add their own adapters and feature rules. This is
narrower than a universal Roblox anti-cheat but produces evidence we can
actually evaluate.

Roblox references: [server-side security tactics](https://create.roblox.com/docs/scripting/security/security-tactics),
[movement/network ownership](https://create.roblox.com/docs/scripting/security/network-ownership),
and [in-game HTTP requests](https://create.roblox.com/docs/cloud-services/http-service).
