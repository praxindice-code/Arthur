# ArthurAI Test Range

Open `ArthurAI-Test-Range.rbxlx` in Roblox Studio using **File > Open from File**, then press **Play**. This is a separate copy of the obby; it does not change your original game or the earlier observer copy. The older `BayesGuard-Test-Range.rbxlx` remains untouched for compatibility; do not open it when testing the latest version.

Your avatar moves to a black, grey, and white test arena. Fourteen labeled dummy characters run automatically. After about 30 seconds, the board should say **14 / 14 PASS**. Walk forward to see the lanes; use the white post's **E** prompt to replay. Studio's **Output** panel lists each case and any script errors. The template's existing `CharacterLeanScript` warning is unrelated to ArthurAI.

The cases are ordinary running, fast dashing, a long fall, spawn grace, moving-platform grace, one isolated strange jump, repeated teleports, repeated upward jumps, an exact speed-limit boundary, long sampling gaps, expired old spikes, reset history, review cooldown, and separation of two actors' histories. Pass means the detector matched the expected answer—not that it has identified a real cheater.

## Test two actual Studio clients

In Studio, select **Test > Server & Clients** with **2 clients**, then start the session. On one client, walk to the white **Two-player check** post near the starting line and press **E**. Keep the other player's character still. The server moves only the first player eight times. After roughly 12 seconds, the post should say **PASS: A reviews > 0, B reviews = 0**, and Output prints an `[ArthurAI multi-client]` result. This tests that the live `Player` observer keeps separate histories; the visible dummies alone cannot test that. The server itself creates the jumps, so this is **not** a real exploit or bypass test. The post works only in Studio, and only after you deliberately start it.

## Measure normal-play alerts

The white **Normal-play trial** post starts an opt-in, two-minute session. It sends the player back to the obby. Play normally without deliberately exploiting. If the same character survives, stays for two minutes, and moves for at least 20 sampled seconds, the game counts one completed trial and returns the player to the range. A trial with one or more review warnings counts as “reviewed.” Death, leaving, respawning, or idling makes the trial incomplete and excludes it from the denominator. The post shows **completed sessions**, **reviewed sessions**, and their percentage; Output also shows review-event totals. Dummies and the two-player synthetic test do **not** enter these trial counts. All counts live only in that running server and reset when it closes; nothing is uploaded or stored permanently.

That percentage is a **normal-play alert proxy**, not yet a proven false-positive rate. A human must confirm that each tested session was legitimate before calling its alert false. A handful of self-tests is not enough to estimate a release-quality rate. For an initial pilot, aim for many varied, consented play sessions across different devices, connections, and obby sections, and inspect every alert before changing thresholds or enabling any enforcement. The test range never kicks or bans anyone.

## What is shared

- `test-range/MovementDetector.lua` makes the movement decision from a timed sequence of positions.
- `test-range/BayesGuardRange.server.lua` creates and moves the visible dummies, feeds their traces into that same detector, and shows pass/fail results.
- `test-range/RangeLiveObserver.server.lua` samples actual players on the server and feeds the same detector. It only writes review warnings to Output.
- `test-range/RangeExperiments.server.lua` provides the opt-in two-client and normal-play posts and session-only counters.

The dummies are models, **not** fake Roblox `Player` objects. They test the scoring logic deterministically. The two-client check adds real Studio `Player` instances, but still does not test realistic lag, genuine cheat software, false alarms across thousands of real sessions, or resistance to bypasses. No one is kicked or banned; nothing is uploaded to a service.

This test range is a demonstrable prototype, not yet a production anti-cheat. The Rust/Zig scorer and offline viewer are still separate from the Roblox place. Before a real developer release, we need a secure hosted gateway, an in-game-to-backend event path, durable review dashboard, privacy/retention policy, and measured false-positive rates. Bayesian optimization becomes useful after obtaining labeled sessions; it does not make these fourteen scripted examples representative of real players.
