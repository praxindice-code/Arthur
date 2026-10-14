# ArthurAI: security boundaries and release gates

This document distinguishes implemented protections from production requirements. The current V2 pilot is **private-test, review-only**. It is not suitable for a 3,000-concurrent-player live experience.

## Trust boundaries

- **Player device:** untrusted. No detection decision, secret, or model is placed in a LocalScript. A client handshake or encrypted client message cannot establish that the client is honest.
- **Roblox game server:** trusted for collection, but the *game* must validate important requests and outcomes. ArthurAI's optional hooks only record that a server handler rejected an action; they do not perform the validation.
- **ArthurAI backend:** not yet deployed. The old Rust loopback service and HTTPS-oriented SDK are prototypes, not a connected production gateway. Do not expose the loopback service to the internet or put a shared secret in client code.

For a future backend, require HTTPS, an authenticated game-server identity stored with Roblox's server-side secret facility, key rotation, request-size limits, replay/idempotency handling, per-game isolation, encryption at rest, short retention, deletion, and access logs. Prefer proven platform cryptography; do not create a custom client cryptographic handshake. These controls protect telemetry, **not** the legitimacy of gameplay actions.

## What is implemented now

- Explicit per-Script opt-in; no kicks, bans, or automatic rollback.
- Server-only sampling and optional server-verified outcome/context hooks (`remote_reject`, `reward_mismatch`, `invalid_hit`, approved movement, ragdoll/vehicle context).
- No player name, UserId, chat, precise position, or remote argument in shared V2 rows.
- Server-only `ArthurAIWindow` callback can associate an anonymous row with a Player for a private review workflow.
- Finite-value checks for positions and velocities, short respawn grace, bounded counters, watched-remotes limit, and a clearly warned Output limit.
- V1/V2/V3 schema validation, per-game/context separation, session-level held-out evaluation, and no automatic promotion of optimized settings.

## What is *not* implemented

- Durable delivery, HTTPS ingestion gateway, encrypted storage, deletion workflow, hosted Rust scoring, live reviewer UI, per-game policy registry, automated drift monitoring, or a real-data-trained Mamba model.
- Robust evidence that false alerts are rare in any real Roblox experience. Passing software tests is not detection validation.
- A universal interpretation of each game's abilities or transactions. Developers must supply a few game-specific server assertions for meaningful coverage.

## Release gates

1. **Private Studio test:** Install both scripts in a copy of a consenting developer's place; verify Luau runtime, join/leave, respawn, legitimate teleport, normal remote use, bad values, and that gameplay is unchanged. Test the server-only callback. No live players.
2. **Controlled cases:** Independently label normal play and deliberately invalid server requests. Include lag, mobile devices, low FPS, vehicles, physics impulses, special abilities, and game updates. Do not label a player “cheating” solely because ArthurAI's score is high.
3. **Measurement:** Report false review alerts per *player-hour*, recall of controlled cases, time to review, performance overhead, missing telemetry, and dropped batches. At 3,000 sustained concurrent players there are 72,000 player-hours/day; even one false alert per 1,000 player-hours would produce about 72 alerts/day.
4. **Backend hardening:** Build and test authenticated, rate-limited HTTPS ingestion and durable queues before any live shadow trial. A full-game pilot cannot use Studio Output as a database.
5. **Limited shadow rollout:** With developer approval and appropriate notice, observe a small cohort without enforcement. Review cases manually and monitor per-device/per-mode false alerts. Stop if overhead, privacy, or false-alert guardrails fail.
6. **Only after independent evidence:** Consider a versioned review policy. Any actual enforcement must be a separate owner-approved decision backed by game-specific server-authoritative checks and a rollback/appeal process.

Bayesian optimization searches policy settings on training data; it does not make a missing label or flawed game rule disappear. A tiny test set cannot certify safety. If zero false alerts occur in *n* independent normal sessions, a one-sided 95% upper bound on the session-level false-alert probability is `1 - 0.05^(1/n)`; the importer reports this as a caution, not a release approval.
