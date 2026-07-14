"""Demo 3 — Trigger/cron loop (error-driven PR generation).

Article section: "Loops developers actually use — triggers and cron jobs"
and the "PR generation from errors" case study (Ivan Pantić's workflow).

A real inbox/ directory fills up with error-event files, exactly the way a
Sentry webhook would drop them. Each tick, the loop drains the oldest
unprocessed event: if no PR exists yet for that error's signature, it opens
one; if a PR already exists (the same bug firing again), it dedups instead
of opening a second one; and if a PR sits open past a few ticks with no
resolution, it logs a real Slack-style notification — the same "notify if
stuck" rule from the article's example.
"""

import json
import tempfile
from pathlib import Path

from loop_harness import Action, LoopRunner, ScriptedModel, Toolbox, Trace

EVENTS = [
    ("err_001.json", {"signature": "KeyError:currency", "trace": "payments.py:42"}),
    ("err_002.json", {"signature": "TimeoutError:db_pool", "trace": "db.py:118"}),
    ("err_003.json", {"signature": "KeyError:currency", "trace": "payments.py:42"}),  # same bug again
    ("err_004.json", {"signature": "KeyError:currency", "trace": "payments.py:44"}),  # again
    ("err_005.json", {"signature": "NullPointer:cart_id", "trace": "cart.py:9"}),
]

NOTIFY_AFTER_TICKS = 3


class TriageToolbox(Toolbox):
    """Adds one real tool, `triage_next`, that does the actual dedup/PR/notify work."""

    def __init__(self, workspace: Path):
        super().__init__(workspace)
        self.pr_age: dict[str, int] = {}

    def triage_next(self) -> str:
        inbox = sorted((self.workspace / "inbox").glob("*.json"))
        if not inbox:
            return "inbox empty, nothing to triage"

        event_path = inbox[0]
        event = json.loads(event_path.read_text())
        signature = event["signature"]
        safe_name = signature.replace(":", "_")
        pr_path = self.workspace / "prs" / f"{safe_name}.md"

        if pr_path.exists():
            seen = int(pr_path.read_text().splitlines()[1].split(":")[1].strip()) + 1
            pr_path.write_text(
                f"# PR: fix {signature}\nseen: {seen}\ntrace: {event['trace']}\nstatus: open (duplicate reports)\n"
            )
            result = f"duplicate of open PR for {signature} (seen {seen}x) -- no new PR opened"
        else:
            pr_path.parent.mkdir(exist_ok=True)
            pr_path.write_text(f"# PR: fix {signature}\nseen: 1\ntrace: {event['trace']}\nstatus: open\n")
            self.pr_age[signature] = 0
            result = f"no existing PR for {signature} -- opened prs/{safe_name}.md"

        (self.workspace / "processed").mkdir(exist_ok=True)
        event_path.rename(self.workspace / "processed" / event_path.name)

        notified = []
        for sig in list(self.pr_age):
            self.pr_age[sig] += 1
            if self.pr_age[sig] == NOTIFY_AFTER_TICKS:
                with (self.workspace / "notifications.log").open("a") as f:
                    f.write(f"[slack] PR for {sig} has been open {NOTIFY_AFTER_TICKS} ticks with no review -- pinging on-call\n")
                notified.append(sig)

        if notified:
            result += f"; notified on-call for: {', '.join(notified)}"
        return result


def build_script() -> list[Action]:
    return [
        Action(
            thought=f"New trigger fired: {filename} landed in inbox/. Triage the oldest pending event.",
            tool="triage_next", args={},
        )
        for filename, _ in EVENTS
    ]


def inbox_drained(toolbox: Toolbox) -> tuple[bool, str]:
    remaining = list((toolbox.workspace / "inbox").glob("*.json"))
    if remaining:
        return False, f"{len(remaining)} event(s) still waiting in inbox/"
    opened = list((toolbox.workspace / "prs").glob("*.md"))
    return True, f"inbox drained -- {len(opened)} distinct PR(s) open from {len(EVENTS)} raw events"


def main() -> None:
    trace = Trace(agent="triage", color="\033[34m")
    trace.banner(
        "DEMO 3 — Trigger / Cron Loop",
        "error events -> triage -> dedup -> PR -> notify if stuck",
    )
    trace.intro(
        what="The 'triggers and cron jobs' pattern: rather than a human watching an "
             "error tracker, a loop wakes on each event (or on a schedule) and reacts. "
             "This mirrors the article's Sentry-to-PR workflow directly.",
        watch=f"{len(EVENTS)} real error-event files land in inbox/, three of which are "
              "the same underlying bug firing again. The loop opens one PR per distinct "
              "signature, dedups repeat reports into the existing PR instead of opening "
              "duplicates, and fires a real notification once a PR has sat open too long.",
    )

    with tempfile.TemporaryDirectory(prefix="loop_demo3_") as ws:
        toolbox = TriageToolbox(Path(ws))
        for filename, event in EVENTS:
            toolbox.write(f"inbox/{filename}", json.dumps(event))

        runner = LoopRunner(
            model=ScriptedModel(build_script()),
            toolbox=toolbox,
            trace=trace,
            predicate=lambda: inbox_drained(toolbox),
            max_ticks=len(EVENTS),
        )
        runner.run()

        prs = sorted((toolbox.workspace / "prs").glob("*.md"))
        notifications_path = toolbox.workspace / "notifications.log"
        notifications = notifications_path.read_text() if notifications_path.exists() else ""

        trace.section("final state on disk")
        trace.note(f"{len(prs)} distinct PR file(s) from {len(EVENTS)} raw events (dedup worked)")
        for pr in prs:
            status_line = pr.read_text().splitlines()[3]
            trace.note(f"  {pr.name}: {status_line}")

        ok = len(prs) == 3 and notifications.strip() != ""
        trace.verdict(ok, "3 distinct PRs opened (not 5) AND a stuck-PR notification actually fired")

    trace.takeaway([
        "Dedup by signature, not by raw event -- three occurrences of one bug became one PR.",
        "The notification rule ('ping if stuck after N ticks') is a real counter, checked every tick, not a one-off.",
        "This is the same loop shape as demo 1 and 2 -- only the trigger source and predicate changed.",
    ])


if __name__ == "__main__":
    main()
