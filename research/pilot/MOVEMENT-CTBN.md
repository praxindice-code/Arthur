# Movement-only CTBN experiment

ArthurAI now has an **offline movement CTBN factor** in [movement_ctbn.py](movement_ctbn.py). It is an experiment, not the live Roblox detector.

Think of the V3 HMM input as one photograph every ten seconds. The CTBN needs a short timeline: “ordinary grounded movement for 8 seconds, fast grounded movement for 1 second, then ordinary again.” It models **how often movement changes state and how long each state lasts**, separately for each server-verified context. The current V3 maximum-per-window logs cannot reconstruct that timeline.

## What the small model does

- One movement node has three speed bands: `idle`, `ordinary`, `fast`. `band_speed()` assigns these using the **new game's own learned speed limit**, not one speed limit copied from a different game.
- The node's transition rates depend on `grounded`, `airborne`, `ragdoll`, or `vehicle` context. Custom ragdoll/vehicle context must come from the game's server-owned hooks, not from a client's claim.
- `fit_normal()` learns rates from *reviewed normal* sessions only. A context needs at least two sessions and 20 observed seconds to be included; these tiny values are software-test gates, not production evidence.
- `score()` reports a movement-trace log-likelihood and how much time the model could cover. It **does not output a probability of cheating or trigger an alert**. Unknown or sparse contexts remain unscored.

This is one conditional-intensity factor of a CTBN, **not yet a full multi-node CTBN**. A future graph could include independently validated shot, reward, or remote-action nodes, but each new node increases data and inference requirements. We add one only if it improves held-out detection without raising false alerts or resource costs.

## Run the offline tests

From the project directory:

```powershell
python -m unittest tests.test_movement_ctbn -v
python -m unittest discover -s tests -q
```

The tests compare ordinary movement with an unusually long fast-grounded spell, show that fast movement during a verified ragdoll has different learned rates, and check that unsupported contexts abstain.

## What must happen before a Roblox trial

1. Add a **private-test-only**, bounded telemetry format that records a sequence of movement-band changes with elapsed times. Avoid raw coordinates, names, client claims, and unlimited event logs. Keep the existing V3 collector as the stable review-only pilot until this format is tested in Studio.
2. Derive band boundaries from normal training sessions only; freeze them before evaluating held-out sessions. Collect legitimate launches, ragdolls, latency spikes, and respawns.
3. Compare this CTBN factor with simple duration rules and the current HMM on unseen sessions. Measure false alerts per player-hour, detection delay, CPU, memory, and telemetry volume. A raw log-likelihood is not a ban policy.

There is no need to train on a GPU or use Bayesian optimization for this prototype. The hard work is trustworthy game context and representative evaluation.
