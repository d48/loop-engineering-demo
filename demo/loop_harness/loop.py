"""LoopRunner — the mechanism the whole article is actually about.

Every "loop engineering" example in the source article — the Ralph Wiggum
loop, Codex's /goal, Claude Code's /goal, a cron job, a Sentry trigger —
reduces to the same shape: repeat scripted turns against a real toolbox
until a real, computed predicate says the goal is met, or a turn budget
runs out. This class is that shape, with nothing else added.

A single fixed "prompt" (do this next thing, once) is just this same
runner with a budget of 1 and no predicate — which is exactly the contrast
demo 2 draws directly.
"""

from dataclasses import dataclass

from .model import ScriptedModel
from .tools import Toolbox
from .trace import Trace


@dataclass
class LoopResult:
    goal_met: bool
    ticks_used: int
    final_status: str


class LoopRunner:
    def __init__(
        self,
        model: ScriptedModel,
        toolbox: Toolbox,
        trace: Trace,
        predicate,
        max_ticks: int = 20,
    ):
        self.model = model
        self.toolbox = toolbox
        self.trace = trace
        self.predicate = predicate  # () -> (bool, str) -- goal met?, human-readable status
        self.max_ticks = max_ticks

    def run(self) -> LoopResult:
        for tick in range(1, self.max_ticks + 1):
            self.trace.tick(tick, self.max_ticks)

            action = self.model.next_action()
            if action is None:
                self.trace.note("script exhausted before goal was met")
                break

            self.trace.thought(action.thought)
            if action.tool:
                detail = ", ".join(f"{k}={self._short(v)}" for k, v in action.args.items())
                self.trace.tool(action.tool, detail)
                try:
                    observation = self.toolbox.call(action.tool, **action.args)
                except Exception as exc:
                    observation = f"TOOL ERROR: {exc}"
                self.trace.observation(observation)

            met, status = self.predicate()
            self.trace.predicate(met, status)
            if met:
                self.trace.final(f"goal met after {tick} tick(s): {status}")
                return LoopResult(goal_met=True, ticks_used=tick, final_status=status)

        met, status = self.predicate()
        return LoopResult(goal_met=met, ticks_used=self.max_ticks, final_status=status)

    @staticmethod
    def _short(value, limit: int = 60) -> str:
        text = repr(value)
        return text if len(text) <= limit else text[: limit - 3] + "..."
