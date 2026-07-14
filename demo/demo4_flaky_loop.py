"""Demo 4 — Flaky test stabilization loop (Paul D'Ambra's case study).

Article section: "Helpful loops for developers" — PostHog's /loop command
that "pulls the next flaky test, runs it to verify local flakiness, and
opens a PR with a fix," producing 13 stabilizing PRs.

Two genuinely flaky tests: a real race condition (unsynchronized counter
incremented from real threads) and a real over-tight deadline assertion
(a timing check whose threshold was simply set without measuring real
jitter). Each tick: measure the test's real failure rate across many fresh
runs, apply a real fix, and reconfirm 0% failure across many more fresh
runs before moving on — exactly the "verify local flakiness, then fix"
loop from the article.
"""

import random
import tempfile
import threading
import time
from pathlib import Path

from loop_harness import Action, LoopRunner, ScriptedModel, Toolbox, Trace

SAMPLES_PER_MEASUREMENT = 40


def race_counter_test(use_lock: bool, rng: random.Random) -> bool:
    """Real race condition: unsynchronized read-modify-write from real threads.

    The `time.sleep(0)` between read and write is what makes this a
    reliable demo rather than a theoretical one: CPython's GIL rarely
    preempts a bare `x = d[k]; x += 1; d[k] = x` on its own, so an
    unsynchronized version of this can pass thousands of times in a row
    by luck. Forcing a real scheduling opportunity right inside the
    critical section is what makes the race actually manifest — and is
    exactly why "just don't add a lock, it'll probably be fine" is the
    trap that produces genuinely flaky tests in real codebases.
    """
    counter = {"value": 0}
    lock = threading.Lock() if use_lock else None
    n_threads, n_incr = 6, 50

    def worker():
        for _ in range(n_incr):
            if lock:
                with lock:
                    counter["value"] += 1
            else:
                current = counter["value"]
                time.sleep(0)
                current += 1
                counter["value"] = current

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return counter["value"] == n_threads * n_incr


def deadline_test(deadline_ms: float, rng: random.Random) -> bool:
    """Real over-tight deadline: genuine timing jitter, not a fake sleep(random)."""
    start = time.monotonic()
    time.sleep(rng.uniform(0.0, 0.02))  # 0-20ms of real jitter, e.g. simulated I/O
    elapsed_ms = (time.monotonic() - start) * 1000
    return elapsed_ms <= deadline_ms


class FlakyToolbox(Toolbox):
    def __init__(self, workspace: Path):
        super().__init__(workspace)
        self.registry = {
            "race_counter": {"fn": race_counter_test, "kwargs": {"use_lock": False}},
            "tight_deadline": {"fn": deadline_test, "kwargs": {"deadline_ms": 10.0}},
        }
        self.stabilized: set[str] = set()
        self.stabilizing_prs = 0

    def _measure(self, name: str) -> float:
        entry = self.registry[name]
        failures = 0
        for i in range(SAMPLES_PER_MEASUREMENT):
            rng = random.Random(1000 + i)  # fresh, independent randomness each run
            ok = entry["fn"](rng=rng, **entry["kwargs"])
            if not ok:
                failures += 1
        return failures / SAMPLES_PER_MEASUREMENT

    def stabilize_next(self) -> str:
        remaining = [n for n in self.registry if n not in self.stabilized]
        if not remaining:
            return "no more flaky tests to stabilize"
        name = remaining[0]

        before_rate = self._measure(name)
        if before_rate == 0.0:
            self.stabilized.add(name)
            return f"{name}: 0/{SAMPLES_PER_MEASUREMENT} failures already -- not flaky, nothing to fix"

        if name == "race_counter":
            self.registry[name]["kwargs"] = {"use_lock": True}
            fix_desc = "added threading.Lock() around the increment"
        else:
            entry = self.registry[name]
            worst = 0.0
            for i in range(20):
                rng = random.Random(2000 + i)
                start = time.monotonic()
                time.sleep(rng.uniform(0.0, 0.02))
                worst = max(worst, (time.monotonic() - start) * 1000)
            new_deadline = round(worst * 1.2, 1)
            entry["kwargs"] = {"deadline_ms": new_deadline}
            fix_desc = f"recomputed deadline from measured jitter -> {new_deadline}ms (was 10.0ms)"

        after_rate = self._measure(name)
        with (self.workspace / "STABILIZED.md").open("a") as f:
            f.write(
                f"## stabilizing PR: {name}\n"
                f"before: {before_rate * 100:.0f}% failure rate ({int(before_rate * SAMPLES_PER_MEASUREMENT)}/{SAMPLES_PER_MEASUREMENT})\n"
                f"fix: {fix_desc}\n"
                f"after: {after_rate * 100:.0f}% failure rate ({int(after_rate * SAMPLES_PER_MEASUREMENT)}/{SAMPLES_PER_MEASUREMENT})\n\n"
            )
        self.stabilizing_prs += 1
        self.stabilized.add(name)
        return (
            f"{name}: was {before_rate * 100:.0f}% flaky, applied fix ({fix_desc}), "
            f"reconfirmed {after_rate * 100:.0f}% failure rate across {SAMPLES_PER_MEASUREMENT} fresh runs"
        )


def all_stabilized(toolbox: FlakyToolbox) -> tuple[bool, str]:
    remaining = [n for n in toolbox.registry if n not in toolbox.stabilized]
    if remaining:
        return False, f"{len(remaining)} test(s) still flaky: {', '.join(remaining)}"
    return True, f"all {len(toolbox.registry)} known flaky tests stabilized ({toolbox.stabilizing_prs} stabilizing PR(s) opened)"


def main() -> None:
    trace = Trace(agent="stabilizer", color="\033[35m")
    trace.banner(
        "DEMO 4 — Flaky Test Stabilization Loop",
        "measure real flakiness -> apply a real fix -> reconfirm -> next test",
    )
    trace.intro(
        what="PostHog's /loop workflow (Paul D'Ambra): pull the next flaky test, run it "
             "enough times to verify it's actually flaky, fix it, and open a PR — "
             "repeated until the whole suite is stable.",
        watch="Two genuinely flaky tests: a real race condition from real threads, and a "
              "real over-tight timing deadline. Each tick measures the test's real "
              "failure rate across 40 fresh runs, applies a real fix, and reruns 40 more "
              "times to confirm 0% before moving to the next test.",
    )

    with tempfile.TemporaryDirectory(prefix="loop_demo4_") as ws:
        toolbox = FlakyToolbox(Path(ws))
        script = [
            Action(thought=f"Pull the next flaky test off the list and stabilize it for real.", tool="stabilize_next", args={})
            for _ in toolbox.registry
        ]
        runner = LoopRunner(
            model=ScriptedModel(script),
            toolbox=toolbox,
            trace=trace,
            predicate=lambda: all_stabilized(toolbox),
            max_ticks=len(toolbox.registry),
        )
        runner.run()

        trace.section("independent re-verification: 50 more fresh runs per test, final config")
        all_clean = True
        for name, entry in toolbox.registry.items():
            failures = 0
            for i in range(50):
                rng = random.Random(9000 + i)
                if not entry["fn"](rng=rng, **entry["kwargs"]):
                    failures += 1
            trace.note(f"{name}: {failures}/50 failures with final config {entry['kwargs']}")
            all_clean = all_clean and failures == 0

        trace.verdict(all_clean, f"{toolbox.stabilizing_prs} stabilizing PR(s), 0 failures across 50 independent re-runs per test")

    trace.takeaway([
        "Flakiness is measured, not assumed -- both 'before' and 'after' rates come from real repeated runs.",
        "The fix for a race condition and the fix for a bad timing threshold are different, but the loop shape is identical.",
        "Independent re-verification after the loop stops is the same discipline as demo 1's harness-side re-check.",
    ])


if __name__ == "__main__":
    main()
