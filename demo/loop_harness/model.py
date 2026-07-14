"""The "model": a deterministic script of thoughts and tool calls, replayed
one tick at a time.

A real harness would call out to an LLM here. For a reproducible, key-free
demo we replay a plausible turn sequence instead — the loop mechanics
around it (fresh context per tick, real predicate checks, real budget)
don't know or care that the turns are scripted.
"""

from dataclasses import dataclass, field


@dataclass
class Action:
    thought: str
    tool: str | None = None
    args: dict = field(default_factory=dict)


class ScriptedModel:
    def __init__(self, script: list[Action]):
        self.script = list(script)
        self.cursor = 0

    def exhausted(self) -> bool:
        return self.cursor >= len(self.script)

    def next_action(self) -> Action | None:
        """Every tick gets a fresh call — nothing here remembers earlier ticks.

        That's the point: like `cat PROMPT.md | claude-code` restarting with
        zero conversation history each time, this model only "remembers"
        what the loop chooses to hand it (usually nothing but the script
        position) — real memory has to come from files, checked by the
        predicate, not from context.
        """
        if self.exhausted():
            return None
        action = self.script[self.cursor]
        self.cursor += 1
        return action
