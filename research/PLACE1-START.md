# Your first BayesGuard obby test

Open `Place1-BayesGuard.rbxlx` in Roblox Studio with **File > Open from File**. This is a separate copy of your place; your original `Place1.rbxl` was not changed.

Press **Play**. Open **View > Output** if the Output panel is hidden. You should see:

`[BayesGuard] Place1 obby observer ready; no enforcement enabled`

The new `Place1ObbyObserver` Script is in **ServerScriptService**. It samples player positions on the *server* twice a second. Three very large horizontal or upward movements within 12 seconds produce a review warning in Output. It ignores the first three seconds after spawn, long downward falls, and the template's moving platforms. It never kicks, bans, or changes gameplay. Ordinary play usually produces no warning, which is expected.

This is an intentionally narrow first sensor, not a full anti-cheat. The template's `Checkpoint` parts belong to moving-platform paths; they are not player progress checkpoints. This place has no finish-line or player checkpoint system to validate yet. Its coin-collection server script already checks coin tags, duplicate pickups, and distance. The observer currently does **not** send data to the BayesGuard viewer or Rust scorer, and no Bayesian optimization is running in Studio. Connecting those pieces requires a hosted HTTPS service and careful testing with real, permissioned game data.

To add a legitimate server teleport later, set `character:SetAttribute("BayesGuardMovementGraceUntil", time() + 2)` before moving the character so the observer does not treat it as suspicious. Keep this tool review-only until its false-alert rate has been measured.
