# ArthurAI architecture, explained simply

## The idea

Imagine a referee who watches a **film** of what a player did. One odd jump may be a lag spike or a built-in teleport. A pattern of unusual actions over several moments is more interesting. The sequence model is the referee's memory. Bayesian optimization (BO) is a careful **settings search** for that referee, not the referee itself.

The setup must not ask whether the game is an obby, shooter, or tycoon. One server-side installer can collect basic signals in any Roblox game. But “works in any game” means **can observe and start in review mode**, not “automatically understands every game's rules or accurately bans cheaters.” Server-authoritative game logic remains the strongest defense; ArthurAI would supplement it.

```text
Roblox game server (Luau universal collector + optional server-only context hooks)
    ↓ bounded anonymous windows
ingestion / storage (future hosted service; today: Output log import)
    ↓ per-game, per-context movement baselines fitted on reviewed normal sessions
sequence scorer (today: pilot-only stationary HMM in Python;
                 separate Rust prototype is not connected yet)
    ↓ risk through time
decision policy (threshold + consecutive windows)
    ↓ anonymous offline review examples; no live queue or automatic ban
human review and controlled-test labels
    ↓
offline BO proposes better per-game settings
    ↓ independent validation + untouched test + approval
versioned policy can be rolled out, monitored, and rolled back (future)
```

## What BO actually optimizes

Today, for each game *g*, BO proposes two numbers: suspicion-score threshold **θ** and consecutive high-score windows **k**. The sequential model produces a score `s_t` for each 10-second window; it is **not** a calibrated probability that the player cheated. A review alert fires when `s_t ≥ θ` for `k` windows in a row. BO tries settings, observes a measured objective on **training** sessions, and proposes the next settings using a Gaussian-process surrogate. The current objective rewards F1 and penalizes false alerts and delay. Validation and held-out test sessions are not used for proposing candidates.

The important “helper function” is the **evaluation objective**. It requires verified normal sessions and controlled/confirmed attack sessions with start times. Unlabeled telemetry cannot tell BO whether a quiet setting missed all cheats or whether an aggressive setting annoyed legitimate players. The minimum of 5+5 sessions in code is merely a software smoke test. Before any live enforcement, the owner would need many representative sessions across devices, lag levels, game modes, updates, and legitimate special abilities, plus a conservative false-alert target and human review.

BO does **not yet** tune the HMM transition/emission probabilities or train a new sequence architecture. That can be added later, but first compare the HMM with simple rules and other sequence baselines on the same untouched test set. A GPU is not required for the current small BO search or fixed HMM. More compute is not a substitute for labels.

### How this can become genuinely plug-and-play

1. **Cold start:** Install one Luau package. It reports only safe, bounded server facts and starts in **observe-only** mode. A shared base model can offer a cautious *review* score, but no game-specific accuracy claim.
2. **Learn this game's normal:** Build baselines from consented, reviewed normal sessions. V3 keeps grounded, airborne, ragdoll, and vehicle movement separate, with server-owned hooks for custom mechanics and bounded exemptions for approved launches/teleports. Keep each game's limits and policy separate; never assume a speed or remote rate from one game applies to another. A context without enough normal sessions abstains from a movement accusation. The current robust-statistics calibrator is an early baseline, not the final learned cross-game adapter.
3. **Transfer carefully:** If many developers opt in, aggregate only approved, compatible statistics to set a prior for a new game. The new game's evidence must be allowed to override that prior. Do not move player identity or raw logs between games.
4. **Tune with BO:** For a game with trustworthy normal and controlled/confirmed attack labels, use BO to test threshold, streak, and eventually selected model settings. Evaluate false alerts, missed attacks, and time-to-review on data that BO did not see.
5. **Release safely:** A human owner approves a versioned, review-only policy. Watch it after updates; roll back on drift or false alerts. Enforcement, if ever justified, needs game-specific server-authoritative checks and an appeal path.

So “any Roblox game” is an **installer and learning-loop goal**, not a promise that a zero-data model knows what cheating means everywhere. Reviewed normal data can calibrate a baseline; without verified attack labels, BO cannot measure whether it catches cheats.

## Why a stationary HMM first

The current hidden Markov model uses the same transition and observation tables at every step. That makes it compact, auditable, and useful for low-data experiments. It does not assert that cheats never change: game versions, exploit tactics, and legitimate mechanics evolve. Mamba's *input-dependent* selective state-space parameters do not by themselves make it unsuitable. Mamba-3 is a future benchmark candidate, not a trained or deployed ArthurAI component; it must beat the HMM and simple rules on real, permissioned sessions.

## What each language does

- **Luau** runs inside the Roblox server. The universal pilot observes movement by context and remote volume; an optional server-only module records outcomes of the game's own validation, custom ragdoll/vehicle state, and approved movement. ArthurAI itself never enforces game rules.
- **Python** handles offline log import, validation, label joins, experiments, Bayesian optimization, and research reports. It is not a player-facing anticheat runtime.
- **Rust** already has a native, memory-safe sequential detector and prototype loopback service. The pilot currently uses a separate, four-state HMM in Python because its observations are different; the Rust prototype is **not** processing pilot data. For a real product Rust belongs in a protected backend, not as a Roblox client program. The current service is not a hosted production gateway.
- **Zig** already supplies a fixed-size, bounded event window linked into the Rust prototype. It can be useful for small, predictable native components, but it does not make cheats “uncrackable,” and the present Zig window does not alter the detector's score.

Roblox games cannot simply load arbitrary Rust or Zig binaries into a Luau Script. The security advantage here comes mainly from **server authority, privacy-aware collection, clear game rules, and measured rollout**, not from hiding code in a particular language.

## Current versus required for a real product

| Piece | Status today | Before production |
| --- | --- | --- |
| Generic install | Review-only V3 Luau Script, explicit opt-in, optional server outcome/context hooks | Studio install test on several real games; lifecycle/performance audit |
| Data | Local Output import, anonymous V1/V2/V3 windows; server-only player callback | Authenticated HTTPS gateway, queue, encrypted storage, retention and deletion |
| Sequence detection | Fixed four-state pilot HMM with offline per-game/context movement calibration; separate offline movement CTBN factor experiment | Timed movement telemetry and Studio validation; compare duration rules, HMM, and CTBN on held-out sessions before live scoring |
| BO | Offline threshold/streak research | Enough reviewed labels, cost-aware objective, drift checks, scheduled retuning |
| Decision | Research report only | Review UI, explanations, appeal path, staged rollout and rollback |
| Enforcement | None | Only after game-owner approval and low false-alert rate; server-side checks first |

## Practical next experiment with a friend

Ask for permission to put the review-only Script into a test copy of their experience. You do not need to ask what genre it is to install it. Gather normal play and clearly marked **controlled** test sessions; do not use actual players as unconsenting experiments. Import the prefix-only Output with `python -m pilot.analyze`. Inspect false alerts and missed controlled tests. Adjust collection and game-specific allowances where necessary, then repeat on unseen sessions. That is a real learning loop, but it is not yet a proven “any game” anticheat.
