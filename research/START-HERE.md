# ArthurAI, explained from the beginning

> **New Roblox pilot:** For the game-agnostic, review-only installer and its
> offline Bayesian-optimization workflow, start with [pilot/README.md](pilot/README.md)
> and [ARTHURAI-ARCHITECTURE.md](ARTHURAI-ARCHITECTURE.md). For a live-game
> safety checklist, see [pilot/SECURITY-AND-ROLLOUT.md](pilot/SECURITY-AND-ROLLOUT.md). The older viewer
> described below uses synthetic examples and is not connected to live pilot data.

Imagine a game referee watching a stack of cards. Each card says something the
game server observed: “movement was okay,” “a request was rejected,” or “a
reward did not match the server's records.” The referee reads the cards **in
order**. One odd card is not enough to call someone a cheater. A pattern of
cards can make the referee more concerned.

ArthurAI began as a small, offline version of that idea. Its legacy Python command is:

```powershell
cd research
py -m bayesguard run
```

That command makes `roblox-cheat-defense.html`. Open or refresh that file in a
browser. Select a session, press **Play**, and watch the model's score change.

## The whole trip

```text
Example events made by Python (or your own event file)
                         |
                         v
               Zig checks each event row
                         |
                         v
               Rust reads rows in order
               and calculates model scores
                         |
                         v
               Python puts the results into
               one self-contained HTML page
                         |
                         v
               Your browser draws the graph
               and lets you try alert rules
```

The page's historical Roblox announcements are a separate shelf of sourced
background information. They are **not** cards fed into the model.

## What each part is for

| Part | Kid-sized description | Main file |
| --- | --- | --- |
| Python command | The start button and organizer | `bayesguard/cli.py` |
| Python pipeline | Carries the same cards through every station | `bayesguard/pipeline.py` |
| Example maker | Invents safe, repeatable practice sessions | `bayesguard/roblox.py` |
| Zig validator | Checks that cards have the right shape and event name | `zig-normalizer/main.zig` |
| Rust detector | The referee: updates its estimate after each card | `rust-detector/src/main.rs` |
| Page builder | Puts Rust's answers and the source timeline into HTML | `bayesguard/roblox_viewer.py` |
| Browser code | Draws the graph and responds to clicks | `bayesguard/viewer.js` and `viewer.css` |
| Tests | Check that all the stations agree | `tests/` |

Compiled binaries are not stored in Git. Their source is in the Zig and Rust
files above; see [BUILD.md](BUILD.md) for instructions on another PC.

The project also keeps its earlier cloud-audit experiment (`model.py`,
`sim.py`, `viewer.py`, and the cloud sections of the Rust program). Those are
**not** part of `py -m bayesguard run`; they remain as an older example.

## A closer look at one event

The input is a tab-separated file with one line per event:

```text
practice-session	0	move_ok
practice-session	1	remote_reject
practice-session	2	reward_mismatch
```

The first piece is the session name. The second is its step number, starting
at zero. The third is an event category. The supported categories are
`move_ok`, `action_ok`, `latency_spike`, `movement_violation`, `remote_reject`,
`reward_mismatch`, and `repetitive_timing`. These categories are an **example
contract**, not Roblox's official log format.

Zig rejects unknown event names and badly shaped rows. Python checks that
sessions stay together and steps do not skip. Rust then updates four internal
possibilities: normal play, suspicious movement, invalid requests, and
automation-like timing. After each event, it returns the four estimates and
an overall model score. The same rules are applied at every step, which is
what “time-invariant” means here.

The score is **not** a real-world probability that someone cheated. The
model's numbers were chosen by hand so we can study the architecture. A
network hiccup, accessibility tool, or unusual but legitimate game mechanic
could look suspicious. Never ban a player from this prototype's output.

## What the controls do

- **Play / event slider:** choose which card to inspect.
- **Threshold:** choose how high the score must be before it counts as
  suspicious.
- **Consecutive events:** choose how many suspicious cards in a row are
  required for an alert.

The browser changes only the **alert rule**. It does not retrain or rerun the
Rust detector. Rust's scores were calculated when you ran the command.

## Your own data, later

If you own a Roblox experience and have permission to use its server logs,
convert server-validated observations into the three-column format above.
Then run:

```powershell
py -m bayesguard run --input path\to\your-events.tsv
```

The page will call those sessions **unlabeled** and hide their original
session IDs in the generated HTML. The original input file is not changed.
The app does not connect to Roblox, collect player data, or decide whether an
actual player cheated. Do not put passwords, account details, or other private
information in the event file. The current browser view accepts up to 10,000
events; a truly large dataset needs a separate database-backed explorer.

## Where Bayesian optimization fits

The original project has an optional `roblox-demo` experiment that tries many
threshold/consecutive-event rules and compares them on invented sessions. It
is **not** part of the main run. We are setting it aside until there is good,
authorized, labeled data. This small optimization itself runs on a CPU; a GPU
would matter more for a much larger future model, not for the current alert
rule search.

## What is complete and what is not

Complete now: one local command, one event format, Zig validation, Rust
inference, Python assembly, a browser view of the *same* Rust results, and
cross-language tests.

Not complete: Roblox Studio integration testing, a hosted service,
real-world calibration, an evaluation on consented labeled gameplay, a large
breach database, or any production enforcement system. A breach incident
catalog is different data from gameplay event sequences and should have its
own explorer.

There is now a **local developer-SDK reference path** in
[DEVELOPER-SDK.md](DEVELOPER-SDK.md): a Luau module and a Rust live process with
Zig feature extraction linked in. It has not been hosted or tested in an
actual Roblox experience and is not production-ready.

For the proposed path to a real tool across an obby, shooter, and tycoon,
including meaningful integrated roles for Rust and Zig, read
[PRODUCTION-PLAN.md](PRODUCTION-PLAN.md).
