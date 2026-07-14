"""Demo 1 — The Ralph Wiggum loop (Geoffrey Huntley, mid-2025).

Article section: "Where it began — the 'Ralph Wiggum' loop"

The original technique, verbatim from the article:

    while :; do cat PROMPT.md | claude-code ; done

A persistent PLAN.md is the only thing that survives between iterations —
the model itself is invoked completely fresh each tick, exactly like a new
`claude-code` process reading PROMPT.md from scratch. There is no
conversation history at all; "memory" is entirely the file on disk. The
loop's goal predicate is simply: every plan item is checked off AND the
real test suite passes.
"""

import tempfile
from pathlib import Path

from loop_harness import Action, LoopRunner, ScriptedModel, Toolbox, Trace

PLAN = """\
# PLAN.md
- [ ] implement add(a, b)
- [ ] implement is_palindrome(s)
- [ ] implement flatten(nested_list)
"""

TEST_FILE = '''\
from mathstuff import add, is_palindrome, flatten

def check(actual, expected):
    assert actual == expected, f"expected {expected!r}, got {actual!r}"

check(add(2, 3), 5)
check(is_palindrome("racecar"), True)
check(is_palindrome("hello"), False)
check(flatten([1, [2, 3], [4, [5, 6]]]), [1, 2, 3, 4, 5, 6])
print("all tests passed")
'''

STARTING_MODULE = "# mathstuff.py -- filled in by the loop, one plan item per tick\n"

# Each tick is a *fresh* model invocation: it only ever reads PLAN.md off
# disk (never a running conversation) to decide what to do next.
SCRIPT = [
    Action(
        thought="Fresh tick. Read PLAN.md to see what's left — this is my only memory.",
        tool="read", args={"path": "PLAN.md"},
    ),
    Action(
        thought="First unchecked item: add(a, b). Implement it.",
        tool="append", args={"path": "mathstuff.py", "content": "\ndef add(a, b):\n    return a + b\n"},
    ),
    Action(
        thought="Check off the item I just finished so the next fresh tick knows.",
        tool="edit", args={"path": "PLAN.md", "old": "- [ ] implement add(a, b)", "new": "- [x] implement add(a, b)"},
    ),
    Action(
        thought="Fresh tick. Read PLAN.md again — I don't remember the previous tick happening.",
        tool="read", args={"path": "PLAN.md"},
    ),
    Action(
        thought="Next unchecked item: is_palindrome(s). Implement it.",
        tool="append", args={
            "path": "mathstuff.py",
            "content": "\ndef is_palindrome(s):\n    return s == s[::-1]\n",
        },
    ),
    Action(
        thought="Check it off.",
        tool="edit", args={"path": "PLAN.md", "old": "- [ ] implement is_palindrome(s)", "new": "- [x] implement is_palindrome(s)"},
    ),
    Action(
        thought="Fresh tick. Read PLAN.md.",
        tool="read", args={"path": "PLAN.md"},
    ),
    Action(
        thought="Last unchecked item: flatten(nested_list). Implement it.",
        tool="append", args={
            "path": "mathstuff.py",
            "content": (
                "\ndef flatten(nested):\n"
                "    out = []\n"
                "    for item in nested:\n"
                "        if isinstance(item, list):\n"
                "            out.extend(flatten(item))\n"
                "        else:\n"
                "            out.append(item)\n"
                "    return out\n"
            ),
        },
    ),
    Action(
        thought="Check it off. All plan items should now be done — the harness checks the real "
                "goal predicate after every tick, so it'll catch completion the moment this lands, "
                "whether or not I explicitly re-run the tests myself.",
        tool="edit", args={"path": "PLAN.md", "old": "- [ ] implement flatten(nested_list)", "new": "- [x] implement flatten(nested_list)"},
    ),
]


def plan_and_tests_done(toolbox: Toolbox) -> tuple[bool, str]:
    """The real goal predicate: every plan line checked off AND tests green."""
    plan = toolbox.read("PLAN.md")
    unchecked = plan.count("- [ ]")
    if unchecked > 0:
        return False, f"{unchecked} plan item(s) still unchecked"
    result = toolbox.bash("python3 test_mathstuff.py")
    if not result.startswith("exit=0"):
        return False, "plan fully checked off, but test suite is not green yet"
    return True, "all plan items checked off AND test suite passes"


def main() -> None:
    trace = Trace(agent="ralph", color="\033[33m")
    trace.banner(
        "DEMO 1 — The Ralph Wiggum Loop",
        "while :; do cat PROMPT.md | claude-code ; done",
    )
    trace.intro(
        what="The original loop-engineering technique (Geoffrey Huntley, mid-2025): "
             "restart the agent completely fresh every tick, with a persistent plan "
             "file as the only memory that survives between iterations.",
        watch="A three-item PLAN.md and a completely empty mathstuff.py. Each tick is "
              "a fresh model invocation that only reads PLAN.md off disk — never a "
              "running conversation — implements the next item, and checks it off. "
              "The loop stops only when the plan is fully checked off AND the real "
              "test suite actually passes.",
    )

    with tempfile.TemporaryDirectory(prefix="loop_demo1_") as ws:
        toolbox = Toolbox(Path(ws))
        toolbox.write("PLAN.md", PLAN)
        toolbox.write("mathstuff.py", STARTING_MODULE)
        toolbox.write("test_mathstuff.py", TEST_FILE)

        runner = LoopRunner(
            model=ScriptedModel(SCRIPT),
            toolbox=toolbox,
            trace=trace,
            predicate=lambda: plan_and_tests_done(toolbox),
            max_ticks=10,
        )
        result = runner.run()

        # Harness-side re-check: never trust the loop's own claim.
        final_plan = toolbox.read("PLAN.md")
        final_tests = toolbox.bash("python3 test_mathstuff.py")
        ok = final_plan.count("- [ ]") == 0 and final_tests.startswith("exit=0")
        trace.verdict(ok, "independent re-check: plan complete and tests green on disk")

    trace.takeaway([
        "Nothing survives between ticks except what's written to disk — that's the whole trick.",
        "The loop's stopping condition is a real, computed check, not a claim.",
        "This exact shape — fresh context + persistent plan file — is what /goal later shipped as a first-class command.",
    ])


if __name__ == "__main__":
    main()
