# ArthurAI: movement-first research proposal

**Status: design proposal and offline prototype, not a deployable anti-cheat.** This document is for review and suggestions before we change the Roblox collector or ask another developer to test it.

## The question we are testing

Can a small, server-side, context-aware movement model start in an unfamiliar Roblox experience, learn that game's normal movement, and flag genuinely unusual movement **without mistaking launches, ragdolls, vehicles, lag, or other legitimate mechanics for cheating**? “Plug and play” means a quick, safe *review-only* installation—not automatic knowledge of every game's rules or automatic bans.

We will focus on Roblox first. Minecraft would need a different server adapter and its own evaluation; sharing a statistical idea does not make the Roblox installer portable.

## What exists now versus what is proposed

| Piece | Exists now | Proposed next |
| --- | --- | --- |
| Roblox collector | Opt-in, review-only Luau script; anonymous 10-second movement summaries and limited server-owned context hooks | Private-test-only, bounded timeline of movement changes and elapsed times |
| Game calibration | Separate robust movement limits per game/context, fitted from reviewed normal sessions | Freeze those limits before testing, then use them to form timed movement bands |
| Sequence model | Fixed pilot HMM on 10-second windows | Compare simple duration rules, HMM, and a small movement CTBN on the same held-out sessions |
| CTBN | Offline Python *movement factor* with synthetic tests | Connect to real timed pilot data only after Studio and privacy checks |
| Decisions | Anonymous research reports; no live scoring or enforcement | Explainable review alerts first; no ML-only bans |

The existing [movement CTBN prototype](pilot/movement_ctbn.py) is only one conditional-intensity factor. It is **not a full multi-node network** and is **not connected to the live Roblox script**. Current 10-second maxima cannot tell us how long a player stayed in each movement state, so they cannot honestly be fed into a continuous-time model.

## Proposed movement pipeline

```text
Roblox server observes movement and its own verified game context
    → compact timeline: context + speed sample + elapsed time
    → per-game/context normal limit turns speed into idle / ordinary / fast
    → merge consecutive equal states into timed runs
    → movement CTBN scores how plausible those runs are under normal play
    → independently calibrated review threshold + explanation
    → human review; no automatic ban
```

We do **not** send precise positions, names, chat, or arbitrary remote arguments for this experiment. A fixed event budget, session expiry, input validation, and explicit retention/deletion rules would be required before even a private test. The collector stays on the Roblox server; there is no client-side model or handshake to “protect.”

### What “context” means

The initial contexts are `grounded`, `airborne`, `ragdoll`, and `vehicle`. Grounded/airborne are observations, **not proof that movement is legitimate**. A custom ragdoll or vehicle context must be asserted by the game's server code after the game verifies it. An approved launch or teleport gets a short bounded exemption, not a permanent pass. We reset movement runs at context boundaries so a launch-to-walk transition is not read as an impossible walking speed.

The server must still reject impossible gameplay requests itself. A statistical model supplements that validation; it cannot infer every custom rule from player positions. Roblox's [movement/security guidance](https://create.roblox.com/docs/scripting/security/network-ownership) makes clear that a universal movement rule is difficult across mechanics and latency conditions.

## What the CTBN would learn

For each game and context, the small model estimates how often movement switches among `idle`, `ordinary`, and `fast`, and how long each state usually lasts. For example, “fast for three seconds after a verified ragdoll” may be common, while “fast for three seconds while normally grounded” may be rare. CTBNs represent *when a state changes and what it changes to* using rates conditioned on related states; they need not force all events into identical time windows. [Nodelman, Shelton, and Koller](https://arxiv.org/abs/1301.0591)

The **model structure can be reused** across games. Its speed boundaries, transition rates, and review threshold must adapt to each game. At first, a new game stays review-only; sparse or unknown contexts abstain. Later, with multiple consenting games, we could test a shared prior to improve cold starts, but never treat another game's movement rules as this game's ground truth. This is the key plug-and-play research hypothesis, not an achieved result.

The prototype returns a trace likelihood, **not a calibrated probability of cheating**. A player can be unusual because of a bug, a new ability, or bad network conditions. We must calibrate any review policy on untouched normal data and verified controlled tests. Shelton and Xu used normal-data likelihood in intrusion detection, but that does not validate it for Roblox without Roblox evidence. [Xu and Shelton](https://arxiv.org/abs/1401.3851)

## Data and evaluation plan

1. **Controlled cases:** Use our test experience to create ordinary walking/jumping, legitimate launches, ragdolls, vehicles, respawns, moving platforms, lag-like gaps, and deliberately impossible movement. These establish that the software handles known cases; they do not estimate real-world false-alert rates.
2. **Natural play:** With a developer's permission, collect private or review-only sessions across devices, play styles, and game mechanics. Review normal examples rather than assuming every unlabeled player is normal; otherwise attackers could contaminate calibration.
3. **Holdout:** Split by whole sessions/players and later by game version or time. Freeze limits and model settings before the holdout. Test on unseen legitimate edge cases and controlled/confirmed attacks.
4. **Compare alternatives:** The CTBN must beat or meaningfully complement a simple speed-plus-duration rule and the current HMM. Measure false review alerts **per player-hour**, detection rate by scenario, time to review, coverage/abstentions, CPU, memory, and telemetry bytes. A low average false-alert rate must not hide one badly affected context or game.

The prototype's “two normal sessions and 20 seconds” minimum merely prevents empty tables in tests. It is nowhere near sufficient to claim production safety. We will not optimize a ban function on live players. Roblox recommends server-side validation and proportional, reversible consequences before severe enforcement. [Roblox server-side detection guidance](https://create.roblox.com/docs/scripting/security/server-side-detection)

## Cost and growth

A movement-only CTBN should be small enough to benchmark on CPU, but we have **not measured** the end-to-end Roblox/server cost yet. More nodes are not free: adding aiming, shooting, or economy actions means new verified event hooks, more state combinations, more training evidence, and more ways to double-count one incident. We add a signal only after it improves held-out results within an agreed performance and false-alert budget. Bayesian optimization and a GPU are not required for this first movement experiment.

## Decisions I want your feedback on

1. Should the first target be only ordinary character movement, or include a vehicle/ragdoll-enabled test place immediately?
2. Which legitimate edge case worries you most: flinging, moving platforms, teleports, latency, or custom abilities?
3. Is a *review queue* the desired first product, or should the game immediately block only server-verifiably impossible movement while leaving statistical alerts for review?
4. Should the first comparison target be one unfamiliar Roblox game with strong testing, or several small test games to measure cross-game adaptation?
5. What privacy and retention limits would a developer be comfortable with for timed movement summaries?

The next implementation step—after we agree on those choices—is a bounded timed-movement format in a private test place, then a reproducible HMM/rule/CTBN comparison. No friend-facing live rollout or ban action is implied by this proposal.
