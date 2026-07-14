"""Demo 2 — Goal vs. Prompt (the article's own Codex example, run for real).

Article section: "The /goal command ships in major harnesses"

    Prompt: "do this next thing"
    Goal:   "keep working until this outcome is true"

    "Reduce p95 checkout latency below 120ms on the checkout benchmark
     while keeping correctness suite green" — the article's Codex Goals
     example, verbatim.

Same starting code, run two ways:
  PROMPT MODE — one fixed edit, stop, regardless of what it actually did.
  GOAL MODE   — loop with a real computed predicate (p95 < 120ms AND the
                correctness suite passes) and a real tick budget, exactly
                mirroring "Codex sets budget constraints" / "Claude Code
                auto-clears the goal once its condition is met."

Both p95 latency and correctness are computed from real code — nothing
here is asserted or narrated.
"""

import tempfile
from pathlib import Path

from loop_harness import Action, LoopRunner, ScriptedModel, Toolbox, Trace

CHECKOUT_PY = '''\
TAX_RATE = 0.08

def compute_total(cart_total):
    """Correctness: must always apply tax exactly once."""
    return round(cart_total * (1 + TAX_RATE), 2)

def simulate_latency_ms(rng):
    """Slow path: no caching, full price lookup on every request."""
    return rng.uniform(140, 200)
'''

BENCHMARK_PY = '''\
import random
from checkout import simulate_latency_ms

def p95_ms(n=300, seed=42):
    rng = random.Random(seed)
    samples = sorted(simulate_latency_ms(rng) for _ in range(n))
    return samples[int(0.95 * len(samples)) - 1]

if __name__ == "__main__":
    print(f"p95_ms={p95_ms():.1f}")
'''

CORRECTNESS_PY = '''\
from checkout import compute_total

def check(actual, expected):
    assert abs(actual - expected) < 0.01, f"expected {expected}, got {actual}"

check(compute_total(100), 108.0)
check(compute_total(50), 54.0)
check(compute_total(0), 0.0)
print("correctness OK")
'''

# PROMPT MODE — a single fire-and-forget edit. It goes for the obvious win
# (skip the "slow" lookup) and, in the same rushed pass, "simplifies" tax
# handling — a completely realistic single-shot mistake nobody catches
# because prompt mode never re-checks its own work.
PROMPT_SCRIPT = [
    Action(
        thought="Single prompt: 'make checkout faster'. Apply the obvious fast path "
                "and simplify the total calculation while I'm in there. Ship it.",
        tool="edit",
        args={
            "path": "checkout.py",
            "old": (
                "def compute_total(cart_total):\n"
                "    \"\"\"Correctness: must always apply tax exactly once.\"\"\"\n"
                "    return round(cart_total * (1 + TAX_RATE), 2)\n\n"
                "def simulate_latency_ms(rng):\n"
                "    \"\"\"Slow path: no caching, full price lookup on every request.\"\"\"\n"
                "    return rng.uniform(140, 200)\n"
            ),
            "new": (
                "def compute_total(cart_total):\n"
                "    return cart_total  # tax handled upstream now (removed the lookup)\n\n"
                "def simulate_latency_ms(rng):\n"
                "    return rng.uniform(60, 110)  # fast path, no lookup\n"
            ),
        },
    ),
]

# GOAL MODE — same starting point, but each tick is checked for real before
# the loop decides whether to keep going.
GOAL_SCRIPT = [
    Action(
        thought="Tick 1: try the fast path for latency only. Leave correctness untouched — "
                "don't risk the tax logic just to chase latency.",
        tool="edit",
        args={
            "path": "checkout.py",
            "old": (
                "def simulate_latency_ms(rng):\n"
                "    \"\"\"Slow path: no caching, full price lookup on every request.\"\"\"\n"
                "    return rng.uniform(140, 200)\n"
            ),
            "new": "def simulate_latency_ms(rng):\n    return rng.uniform(90, 150)\n",
        },
    ),
    Action(
        thought="Tick 2: measure. If p95 is still over budget, narrow the range further "
                "and check correctness again before declaring done.",
        tool="edit",
        args={
            "path": "checkout.py",
            "old": "def simulate_latency_ms(rng):\n    return rng.uniform(90, 150)\n",
            "new": "def simulate_latency_ms(rng):\n    return rng.uniform(60, 105)\n",
        },
    ),
]


def goal_predicate(toolbox: Toolbox) -> tuple[bool, str]:
    bench = toolbox.bash("python3 benchmark.py")
    correctness = toolbox.bash("python3 correctness.py")
    p95_line = next((l for l in bench.splitlines() if "p95_ms=" in l), "p95_ms=?")
    p95_value = float(p95_line.split("=")[1])
    latency_ok = p95_value < 120.0
    correctness_ok = correctness.startswith("exit=0")
    if latency_ok and correctness_ok:
        return True, f"p95={p95_value:.1f}ms (<120) AND correctness suite green"
    if not correctness_ok:
        return False, f"p95={p95_value:.1f}ms — but correctness suite FAILED (regression)"
    return False, f"p95={p95_value:.1f}ms — still over the 120ms budget"


def seed_workspace(toolbox: Toolbox) -> None:
    toolbox.write("checkout.py", CHECKOUT_PY)
    toolbox.write("benchmark.py", BENCHMARK_PY)
    toolbox.write("correctness.py", CORRECTNESS_PY)


def run_prompt_mode() -> None:
    trace = Trace(agent="prompt", color="\033[31m")
    trace.section("PROMPT MODE — 'do this next thing', once, then stop")
    with tempfile.TemporaryDirectory(prefix="loop_demo2_prompt_") as ws:
        toolbox = Toolbox(Path(ws))
        seed_workspace(toolbox)
        runner = LoopRunner(
            model=ScriptedModel(PROMPT_SCRIPT),
            toolbox=toolbox,
            trace=trace,
            predicate=lambda: goal_predicate(toolbox),
            max_ticks=1,  # a prompt does one thing and stops, win or lose
        )
        runner.run()
        met, status = goal_predicate(toolbox)
        trace.verdict(False if not met else True, f"final state after one unverified edit: {status}")


def run_goal_mode() -> None:
    trace = Trace(agent="goal", color="\033[32m")
    trace.section("GOAL MODE — 'keep working until this outcome is true'")
    with tempfile.TemporaryDirectory(prefix="loop_demo2_goal_") as ws:
        toolbox = Toolbox(Path(ws))
        seed_workspace(toolbox)
        runner = LoopRunner(
            model=ScriptedModel(GOAL_SCRIPT),
            toolbox=toolbox,
            trace=trace,
            predicate=lambda: goal_predicate(toolbox),
            max_ticks=6,  # a real, honest budget constraint -- matches "Codex sets budget constraints"
        )
        result = runner.run()
        trace.verdict(result.goal_met, f"loop stopped after {result.ticks_used} tick(s): {result.final_status}")


def main() -> None:
    trace = Trace(agent="demo")
    trace.banner(
        "DEMO 2 — Goal vs. Prompt",
        "the article's own Codex example: p95 checkout latency < 120ms, correctness green",
    )
    trace.intro(
        what="The core distinction the /goal command shipped to formalize: a prompt does "
             "one thing and stops; a goal keeps looping, with a real check after every "
             "tick, until the outcome is genuinely true (or a budget runs out).",
        watch="The identical checkout benchmark optimized two ways. Prompt mode fires a "
              "single unverified edit and ships whatever it produces. Goal mode iterates, "
              "checking real p95 latency AND a real correctness suite after every tick, "
              "and only stops once both are genuinely satisfied.",
    )
    run_prompt_mode()
    run_goal_mode()
    trace.takeaway([
        "A prompt is a loop with a budget of 1 and no verification — that's the whole difference.",
        "Prompt mode's single edit hit the latency target but silently broke correctness; nobody checked.",
        "Goal mode's budget is real: it can fail honestly if the outcome never becomes true in time.",
    ])


if __name__ == "__main__":
    main()
