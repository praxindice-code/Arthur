"""Replay normalized local event frames into the local Rust service."""
import argparse
import os
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path, nargs="?", default=Path("roblox-events.tsv"))
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    args = parser.parse_args()
    key = os.environ.get("BAYESGUARD_KEY")
    if not key:
        parser.error("set BAYESGUARD_KEY in the environment")
    rows = [line for line in args.events.read_text(encoding="utf-8").splitlines() if line]
    for start in range(0, len(rows), 50):
        body = ("\n".join(rows[start:start + 50]) + "\n").encode("utf-8")
        request = Request(args.url + "/v1/events", data=body, method="POST",
                          headers={"Content-Type": "text/plain", "x-api-key": key})
        with urlopen(request, timeout=10) as result:
            print(result.read().decode("utf-8"), end="")


if __name__ == "__main__":
    main()
