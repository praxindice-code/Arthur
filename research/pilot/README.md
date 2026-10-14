# ArthurAI universal Roblox pilot

This is a **game-agnostic, review-only data collector**, not a finished anticheat. It can be inserted into an obby, shooter, tycoon, or another Roblox experience without knowing the genre. It observes movement by server-known context and the number of client-to-server `RemoteEvent` calls everywhere. An optional server-only module adds meaningful validation outcomes and custom movement contexts from the game's own code. It does not ban, kick, block remotes, read remote arguments, or send data over the network.

Read [security boundaries and rollout gates](SECURITY-AND-ROLLOUT.md) before asking anyone to test it in an existing experience.

There is also a separate [movement-only CTBN experiment](MOVEMENT-CTBN.md). It needs timed movement traces that this V3 collector does not produce and is **not** running in Roblox.

## Try it in a game you own

1. Open the experience in Roblox Studio. In **Explorer**, add a normal **Script** under **ServerScriptService**. Name it `ArthurAIUniversal` and replace its contents with [ArthurAIUniversal.server.lua](ArthurAIUniversal.server.lua).
2. Select the **ArthurAIUniversal Script** in Explorer. In **Properties → Attributes**, add a Boolean attribute named `ArthurAIPilotEnabled` and set it to `true`. This explicit switch is required. Keep it false until everyone involved approves the pilot.
3. Start a local test server, play normally for a few minutes, and inspect **View → Output**. Look for `ARTHURAI_PILOT_V3` lines. Each is one anonymous 10-second window. An idle or respawning character can produce a zero-sample window.
4. Do controlled test runs, separately from normal-play runs. Write down which anonymous session ID belongs to each *controlled* run and the window number where the test began. Do not infer labels merely from high movement or remote counts.
5. Share **only** lines containing `ARTHURAI_PILOT_V3` with the analyst, after checking your consent and retention rules. Do not share the entire Output, which may contain names or other data from unrelated scripts. For this first pilot, Studio Output or accessible server logs are the transport; this script has no remote collection service.

The script writes a game/universe ID, random session ID, window number, start time, sample count, maximum horizontal/upward movement **separately for grounded, airborne, ragdoll, and vehicle contexts**, remote-call count, ignored-movement count, and counts of server-verified outcomes. It does **not** log player names, Roblox UserIds, chat, precise positions, or remote payloads. Session IDs are not stable across joins. A game owner still needs to give appropriate notice and handle the logs responsibly.

## Optional game-rule hooks

Add [ArthurAIEvents.lua](ArthurAIEvents.lua) as a **ModuleScript** beside the main Script *before* starting the server. The collector works without it, but cannot understand whether a game action was legal. Call the module **only from server code after the game has independently checked an action**:

```lua
local Events = require(game.ServerScriptService.ArthurAIEvents)
-- Within an existing server-side purchase/shooting handler:
if not purchaseAllowed then
    Events.record(player, "remote_reject")
    return -- the game itself rejects the action; ArthurAI never decides this
end
```

The allowed review categories are `remote_reject`, `reward_mismatch`, and `invalid_hit`. They are counts, not client claims or proof of cheating. For a legitimate server-driven teleport, dash, or launch, call `Events.allowMovement(player, seconds)` immediately before moving the character; `seconds` must be greater than 0 and at most 30. This exempts that short period from movement scoring and records the exemption. Do not use the hook to excuse all movement indefinitely. The exemption is kept inside the server collector, not in a replicated character attribute.

The collector distinguishes observed grounded and airborne movement. It does **not** treat client-influenced seating or Humanoid physics state as proof of a legitimate ragdoll or vehicle ride. Those contexts need a small server-side hook after **the game itself verifies the state**:

```lua
-- From your existing server-owned vehicle/ragdoll controller, not a RemoteEvent handler
-- that blindly forwards a client's claim:
Events.setMovementContext(player, "vehicle", 5)
-- Refresh while the player actually remains in the vehicle. Valid for up to 30 seconds.
```

The hook accepts only `"vehicle"` and `"ragdoll"` and a duration above 0 through 30 seconds. Context changes reset the movement segment so a launch-to-walk transition does not create one enormous apparent walking speed. **Do not invoke these hooks solely because a client requested them.**

The collector also creates a server-only `BindableEvent` named `ArthurAIWindow` as a child of its Script. A separate server Script can subscribe to `(player, anonymousWindow)` for a private moderator workflow:

```lua
local collector = game.ServerScriptService:WaitForChild("ArthurAIUniversal")
collector:WaitForChild("ArthurAIWindow").Event:Connect(function(player, window)
    -- Send a case to a private server-side moderator workflow, if you have one.
    -- This is telemetry, not a cheating verdict. Never kick from this callback.
end)
```

**Never put a Player or UserId into the shared pilot log.** No client-side handshake, secret, or model is required. The callback is only an integration point; this project does not yet provide a hosted moderator interface.

## Analyze locally

From the `research/` project folder:

```powershell
python -m pilot.analyze pilot/example-output.log
python -m pilot.analyze path\to\pilot-output.log
```

This validates and counts sessions. It does not claim any cheat detection without labels.

For a labeled research run, create a CSV with exactly these columns:

```csv
game_id,session_id,label,attack_start_window
123,normal-test-session,normal,
123,controlled-test-session,controlled_attack,2
```

The session IDs must exactly match the log. Use at least five reviewed normal and five controlled-attack sessions **per game**; that minimum only exercises the research pipeline and is nowhere near production evidence. Then run:

```powershell
python -m pilot.analyze path\to\pilot-output.log --labels path\to\labels.csv --trials 16 --output path\to\new-results.json
```

The importer accepts V1, V2, and V3 logs, rejects malformed, duplicate, missing, or out-of-range windows, and keeps different games separate. It fits feature limits on training normal sessions only. V3 fits **separate movement limits per context** once at least two normal training sessions and five windows contain that context. That is only a software gate, not enough data for a production claim. Sparse contexts are uncalibrated: their movement does not generate an anomaly signal, although independently verified rejected actions and remote-volume signals can still be reviewed. A fixed time-homogeneous hidden Markov model scores sequences; Gaussian-process Bayesian optimization proposes an alert threshold and required consecutive-window count; validation/held-out test scores and anonymous review examples show which context was above, within, or missing a learned baseline. The model's score is **not** a calibrated cheating probability. When no holdout false alerts occur, the report gives a 95% upper bound on the **session-level** false-alert rate. A tiny holdout still gives a very weak bound. It **never automatically deploys a policy**. The optional output path must not already exist.

## Important limits

- This collector does not know an individual game's intended teleports, dash abilities, firing rate, currencies, or server-side combat rules. A high value is only a reason to review.
- `RemoteFunction`, server-to-client traffic, and application-specific actions are not captured. The general collector alone cannot prove an exploit.
- The V3 collector intentionally does **not** trust a character attribute to authorize movement. Use the server-only `Events.allowMovement` hook for approved teleports and launches.
- V3 context calibration currently covers movement only. Shooting/aiming, economy, and other game-specific mechanics still need validated server hooks and independent evaluation; no single model knows those rules automatically.
- Output is local to a test/server session. It is not a production database or durable delivery mechanism. The collector caps output at 2,000 windows/server, warns when the cap is reached, and watches at most 5,000 RemoteEvents. With 30 players, the output cap is reached in roughly 11 minutes. **Do not install this version in a high-traffic live game.**
- No production false-positive rate, cheat recall, or training time can be honestly promised before representative, permissioned data and independently verified labels exist.
