# Loop Engineering — Demos & Slides

A slide deck and four runnable demos teaching the concepts from
**Gergely Orosz, ["What is 'loop engineering'?"](https://newsletter.pragmaticengineer.com/p/what-is-loop-engineering) (The Pragmatic Engineer, Jul 2026)** —
the Ralph Wiggum loop, the goal-vs-prompt distinction that shipped as `/goal`
across every major coding agent, and the trigger/cron loops developers
actually run in production.

## Quick start

Requires only Python 3.10+ (stdlib only — no packages, no API keys, no network).
`npm install` is not required — `package.json` just wraps the Python entry point
for convenience.

```bash
python3 demo/run.py            # interactive menu
python3 demo/run.py 1          # run one demo
python3 demo/run.py all        # run everything
python3 demo/run.py all --fast # skip the dramatic pauses (smoke test)
```

or, equivalently, via npm:

```bash
npm run demo          # interactive menu
npm run demo:1         # run demo 1 (demo:2 … demo:4 also available)
npm run demo:all       # run everything
npm run slides         # open the deck in your browser
```

## The demos

Every demo is the same core mechanism — `loop_harness.LoopRunner`: repeat
scripted turns against a real toolbox until a real, computed predicate says
the goal is met, or a turn budget runs out. That single class *is* the
article's own definition of the difference between a prompt ("do this next
thing") and a goal ("keep working until this outcome is true"). The "model"
turns are scripted (deterministic, reproducible on stage, no API key
needed), but every file write, subprocess, test run, and predicate check
around them is real.

| # | Demo | Article concept | What actually happens |
|---|---|---|---|
| 1 | `demo1_ralph_loop.py` | The Ralph Wiggum loop | A persistent `PLAN.md` survives across a dozen completely fresh-context ticks; the loop stops only when every item is checked off **and** the real test suite passes |
| 2 | `demo2_goal_vs_prompt.py` | Goal vs. prompt (Codex's own example) | The same checkout-latency benchmark run two ways: a single unverified edit ships a broken "fix," while a goal loop iterates against real p95 latency + a real correctness suite until both are genuinely true |
| 3 | `demo3_trigger_loop.py` | Triggers & cron jobs | Real error-event files land in an inbox; the loop dedups repeat reports into one PR by signature and fires a real notification once a PR sits open too long |
| 4 | `demo4_flaky_loop.py` | Flaky test stabilization (Paul D'Ambra's case) | A genuine race condition (real threads, no lock) and a genuinely over-tight timing deadline get measured, fixed, and reconfirmed at 0% failure across dozens of fresh runs |

## Repo layout

```
demo/
  loop_harness/         # the shared harness: ~200 lines, deliberately simple
    loop.py             # LoopRunner — turns until a real predicate is true, or budget runs out
    tools.py            # real tools: read/write/edit/ls/grep/bash over a sandbox
    model.py            # the scripted "model" (swap for a real LLM here)
    trace.py            # terminal rendering: THOUGHT / TOOL / OBSERVE / GOAL MET / verdicts
  demo1..demo4_*.py      # the four demos
  run.py                 # menu / runner
slides/
  loop-engineering-slides.html  # self-contained deck with diagrams (no dependencies)
  index.html                    # redirects the bare Pages URL to the deck above
.github/workflows/
  pages.yml              # deploys slides/ to GitHub Pages on push to main
```

## Presenting this

Suggested flow for a ~20-minute engineering talk:

1. Slides 1–5: what loop engineering is, and where it came from (Ralph Wiggum, run demo 1).
2. Slides 6–8: `/goal` shipping across every major harness, and the goal-vs-prompt distinction (run demo 2).
3. Slides 9–11: the two loop shapes developers actually use in production, with named case studies (run demos 3 and 4).
4. Slides 12–13: the honest gaps the source article raises, and takeaways.

Every demo ends with a `TAKEAWAY` block that matches the corresponding slide's
speaker notes, so the deck and the terminal reinforce each other.
