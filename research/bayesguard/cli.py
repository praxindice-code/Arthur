"""Command-line experiment and report."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .model import Policy
from .optimize import evaluate, prepare, search
from .sim import make_sessions
from .viewer import create_viewer
from .roblox import make_sessions as make_roblox_sessions, risks as roblox_risks
from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline cloud audit detector prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="tune on training sessions and evaluate holdout")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--train", type=int, default=160)
    demo.add_argument("--test", type=int, default=100)
    demo.add_argument("--trials", type=int, default=16)
    demo.add_argument("--output", type=Path, default=Path("demo-results.json"))
    emit = sub.add_parser("emit", help="write simulated event frames for native tools")
    emit.add_argument("--seed", type=int, default=42)
    emit.add_argument("--sessions", type=int, default=10)
    emit.add_argument("--output", type=Path, default=Path("events.tsv"))
    viewer = sub.add_parser("visualize", help="create an interactive offline HTML viewer")
    viewer.add_argument("--seed", type=int, default=42)
    viewer.add_argument("--sessions", type=int, default=10)
    viewer.add_argument("--threshold", type=float, default=.5)
    viewer.add_argument("--streak", type=int, default=2)
    viewer.add_argument("--output", type=Path, default=Path("bayesguard-viewer.html"))
    roblox = sub.add_parser("run", aliases=["roblox"],
                            help="run Zig validation, Rust detection, and the Roblox viewer")
    roblox.add_argument("--seed", type=int, default=42)
    roblox.add_argument("--sessions", type=int, default=12)
    roblox.add_argument("--threshold", type=float, default=.5)
    roblox.add_argument("--streak", type=int, default=2)
    roblox.add_argument("--input", type=Path, help="optional normalized TSV event file")
    roblox.add_argument("--output", type=Path, default=Path("roblox-cheat-defense.html"))
    roblox_demo = sub.add_parser("roblox-demo", help="tune a policy on synthetic Roblox-inspired sessions")
    roblox_demo.add_argument("--seed", type=int, default=42)
    roblox_demo.add_argument("--train", type=int, default=160)
    roblox_demo.add_argument("--test", type=int, default=100)
    roblox_demo.add_argument("--trials", type=int, default=16)
    roblox_demo.add_argument("--output", type=Path, default=Path("roblox-results.json"))
    roblox_emit = sub.add_parser("roblox-emit", help="write synthetic Roblox event frames for native tools")
    roblox_emit.add_argument("--seed", type=int, default=42)
    roblox_emit.add_argument("--sessions", type=int, default=12)
    roblox_emit.add_argument("--output", type=Path, default=Path("roblox-events.tsv"))
    args = parser.parse_args()
    if args.command in ("run", "roblox"):
        try:
            summary = run_pipeline(args.output, input_path=args.input, seed=args.seed,
                                   sessions=args.sessions, threshold=args.threshold,
                                   streak=args.streak)
        except (ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))
        print(f"Saved {summary.output} from {summary.source} events "
              f"({summary.session_count} sessions, {summary.event_count} events, "
              f"{summary.alert_count} alerting steps)")
    elif args.command == "roblox-emit":
        if args.sessions < 1:
            parser.error("sessions must be positive")
        sessions = make_roblox_sessions(args.sessions, args.seed)
        with args.output.open("w", encoding="utf-8", newline="\n") as output:
            for session in sessions:
                for step, kind in enumerate(session.events):
                    output.write(f"{session.session_id}\t{step}\t{kind}\n")
        print(f"Saved {args.output}")
    elif args.command == "roblox-demo":
        if args.train < 4 or args.test < 4:
            parser.error("train and test must each have at least four sessions")
        training = [(s, roblox_risks(s.events)) for s in make_roblox_sessions(args.train, args.seed)]
        holdout = [(s, roblox_risks(s.events)) for s in make_roblox_sessions(args.test, args.seed + 10000)]
        policies = {}
        traces = {}
        for method in ("bayes", "random"):
            policies[method], traces[method] = search(training, args.trials, args.seed + 1, method)
        policies["fixed"] = Policy(.70, 2)
        results = {
            "warning": "Synthetic gameplay only; scores do not estimate real-world detection quality.",
            "seed": args.seed, "training_sessions": args.train,
            "holdout_sessions": args.test, "trials_per_search": args.trials,
            "methods": {name: {"policy": asdict(policy),
                               "training": asdict(evaluate(training, policy)),
                               "holdout": asdict(evaluate(holdout, policy)),
                               "search_history": traces.get(name, [])}
                        for name, policy in policies.items()},
        }
        args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        for name, row in results["methods"].items():
            m = row["holdout"]
            print(f"{name:6} F1={m['f1']:.3f} recall={m['recall']:.3f} "
                  f"benign-FAR={m['benign_false_alert_rate']:.3f}")
        print(f"Saved {args.output}")
    elif args.command == "visualize":
        try:
            path = create_viewer(args.output, seed=args.seed, sessions=args.sessions,
                                 threshold=args.threshold, streak=args.streak)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Open {path.resolve()} in a browser")
    elif args.command == "emit":
        if args.sessions < 1:
            parser.error("sessions must be positive")
        sessions = make_sessions(args.sessions, args.seed)
        with args.output.open("w", encoding="utf-8", newline="\n") as output:
            for session in sessions:
                for step, kind in enumerate(session.events):
                    output.write(f"{session.session_id}\t{step}\t{kind}\n")
        print(f"Saved {args.output}")
    elif args.command == "demo":
        if args.train < 2 or args.test < 2:
            parser.error("train and test must each have at least two sessions")
        training = prepare(make_sessions(args.train, args.seed))
        holdout = prepare(make_sessions(args.test, args.seed + 10000))
        policies = {}
        traces = {}
        for method in ("bayes", "random"):
            policies[method], traces[method] = search(training, args.trials,
                                                        args.seed + 1, method)
        policies["fixed"] = Policy(.70, 2)
        results = {
            "seed": args.seed,
            "training_sessions": args.train,
            "holdout_sessions": args.test,
            "trials_per_search": args.trials,
            "methods": {
                name: {
                    "policy": asdict(policy),
                    "training": asdict(evaluate(training, policy)),
                    "holdout": asdict(evaluate(holdout, policy)),
                    "search_history": traces.get(name, []),
                } for name, policy in policies.items()
            },
        }
        args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        for name, row in results["methods"].items():
            p, m = row["policy"], row["holdout"]
            print(f"{name:6} threshold={p['threshold']:.2f} streak={p['streak']} "
                  f"F1={m['f1']:.3f} recall={m['recall']:.3f} "
                  f"benign-FAR={m['benign_false_alert_rate']:.3f} "
                  f"delay={m['mean_detection_delay']:.3f}")
        print(f"Saved {args.output}")
