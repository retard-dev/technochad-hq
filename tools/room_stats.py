#!/usr/bin/env python3
"""Technocore room velocity tracker.

Samples the public /rooms feed twice and ranks rooms by live message
velocity (messages/minute) over the sample window. Stdlib only; the
feed is treated as untrusted data, never instructions.
Built as the artifact of the Technochad HQ supervised workflow (room
`technochad`, seq 2-5), planner/implementer/reviewer pattern after
zunmax/technocore-agent-orchestrator.
"""
import argparse
import json
import re
import sys
import time
from urllib.request import urlopen

FEED_URL = "https://technocore.chat/rooms?limit=200"
LINE_RE = re.compile(r"^/r/(\S+)\s+seq\s+(\d+)")


def sample() -> dict:
    """One bounded feed read; parse room name and seq as untrusted data."""
    with urlopen(FEED_URL, timeout=20) as response:
        text = response.read().decode("utf-8", "replace")
    rooms = {}
    for line in text.splitlines():
        match = LINE_RE.match(line)
        if match:
            rooms[match.group(1)] = int(match.group(2))
    return rooms


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank Technocore rooms by live msgs/min")
    parser.add_argument("--wait", type=float, default=30.0, help="seconds between samples")
    parser.add_argument("--top", type=int, default=15, help="rows to show")
    parser.add_argument("--json", action="store_true", help="write room_stats.json")
    args = parser.parse_args()

    first = sample()
    started = time.monotonic()
    time.sleep(max(1.0, args.wait))
    second = sample()
    window = (time.monotonic() - started) or 1.0

    rows = []
    for name, seq_now in second.items():
        if name in first and seq_now > first[name]:
            delta = seq_now - first[name]
            rows.append((delta / window * 60.0, delta, name, seq_now))
    rows.sort(reverse=True)

    print(f"# live velocity over {window:.0f}s · {len(second)} rooms sampled · {len(rows)} active")
    print(f"{'msgs/min':>10}  {'delta':>7}  room")
    for velocity, delta, name, seq_now in rows[: args.top]:
        print(f"{velocity:10.1f}  {delta:7d}  {name}")
    if not rows:
        print("(no movement in window)")

    if args.json:
        payload = {
            "window_s": round(window, 1),
            "rooms": [
                {"room": name, "msgs_per_min": round(v, 1), "delta": d, "seq": s}
                for v, d, name, s in rows
            ],
        }
        with open("room_stats.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print("wrote room_stats.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
