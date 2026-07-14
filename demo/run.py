#!/usr/bin/env python3
"""Runner for the loop-engineering demos.

Usage:
    python3 demo/run.py           # interactive menu
    python3 demo/run.py 1         # run demo 1
    python3 demo/run.py all       # run every demo back to back
    python3 demo/run.py all --fast  # no dramatic pauses (CI / smoke test)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

MENU = """
  Loop Engineering — live demos
  (concepts from Gergely Orosz, "What is 'loop engineering'?", The Pragmatic Engineer, Jul 2026)

    1. The Ralph Wiggum loop     fresh context every tick; a plan file is the only memory
    2. Goal vs. prompt           same task, run once (fire-and-forget) vs looped-until-true
    3. Trigger / cron loop       error events -> dedup -> PR -> notify if stuck
    4. Flaky test stabilization  measure real flakiness -> fix -> reconfirm -> next test

    a. run all      q. quit
"""


def run(number: str) -> None:
    import demo1_ralph_loop
    import demo2_goal_vs_prompt
    import demo3_trigger_loop
    import demo4_flaky_loop

    demos = {
        "1": demo1_ralph_loop.main,
        "2": demo2_goal_vs_prompt.main,
        "3": demo3_trigger_loop.main,
        "4": demo4_flaky_loop.main,
    }
    if number in ("a", "all"):
        for main in demos.values():
            main()
    elif number in demos:
        demos[number]()
    else:
        print(f"unknown demo: {number}")
        sys.exit(2)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--fast"]
    if "--fast" in sys.argv:
        os.environ["DEMO_FAST"] = "1"

    if args:
        run(args[0])
        return

    while True:
        print(MENU)
        choice = input("  choose> ").strip().lower()
        if choice in ("q", "quit", "exit", ""):
            return
        run(choice)


if __name__ == "__main__":
    main()
