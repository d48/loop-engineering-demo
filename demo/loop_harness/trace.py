"""Terminal trace rendering: makes each loop tick legible to an audience."""

import os
import sys
import textwrap
import time

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

USE_COLOR = sys.stdout.isatty() or os.environ.get("FORCE_COLOR") == "1"


def paint(text: str, *codes: str) -> str:
    if not USE_COLOR:
        return text
    return "".join(codes) + text + RESET


class Trace:
    """Prints the anatomy of a loop tick: turn -> tool call -> observation -> predicate check."""

    def __init__(self, agent: str = "loop", color: str = CYAN, delay: float | None = None):
        self.agent = agent
        self.color = color
        if delay is None:
            delay = 0.0 if os.environ.get("DEMO_FAST") == "1" else 0.3
        self.delay = delay

    def _prefix(self) -> str:
        return paint(f"[{self.agent}]", self.color, BOLD)

    def _emit(self, line: str = "") -> None:
        print(line)
        sys.stdout.flush()

    def pause(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    def banner(self, title: str, subtitle: str = "") -> None:
        width = 74
        self._emit()
        self._emit(paint("=" * width, BOLD))
        self._emit(paint(f"  {title}", BOLD))
        if subtitle:
            self._emit(paint(f"  {subtitle}", DIM))
        self._emit(paint("=" * width, BOLD))

    def intro(self, what: str, watch: str) -> None:
        self._emit()
        self._emit(paint("  WHAT THIS IS", MAGENTA, BOLD))
        for line in textwrap.wrap(what, width=70):
            self._emit(f"    {line}")
        self._emit()
        self._emit(paint("  WHAT YOU'LL SEE", MAGENTA, BOLD))
        for line in textwrap.wrap(watch, width=70):
            self._emit(f"    {line}")
        self._emit()

    def section(self, title: str) -> None:
        self._emit()
        self._emit(paint(f"--- {title} ", MAGENTA, BOLD) + paint("-" * max(0, 68 - len(title)), MAGENTA))
        self.pause()

    def note(self, text: str) -> None:
        self._emit(paint(f"    {text}", DIM))

    def tick(self, n: int, budget: int | None = None) -> None:
        self._emit()
        label = f"tick {n}" + (f"/{budget}" if budget else "")
        self._emit(f"{self._prefix()} {paint(label, BOLD)}")

    def thought(self, text: str) -> None:
        self._emit(f"  {paint('THOUGHT', YELLOW, BOLD)}  {text}")
        self.pause()

    def tool(self, name: str, detail: str) -> None:
        self._emit(f"  {paint('TOOL', BLUE, BOLD)}     {paint(name, BOLD)}({detail})")
        self.pause()

    def observation(self, text: str, max_lines: int = 12) -> None:
        lines = text.rstrip().splitlines() or ["(empty)"]
        shown = lines[:max_lines]
        self._emit(f"  {paint('OBSERVE', GREEN, BOLD)}  {shown[0]}")
        for line in shown[1:]:
            self._emit(f"           {line}")
        if len(lines) > max_lines:
            self._emit(f"           {paint(f'... ({len(lines) - max_lines} more lines)', DIM)}")
        self.pause()

    def predicate(self, ok: bool, text: str) -> None:
        tag = paint("GOAL MET", GREEN, BOLD) if ok else paint("NOT YET", YELLOW, BOLD)
        self._emit(f"  {tag}  {text}")
        self.pause()

    def final(self, text: str) -> None:
        self._emit(f"  {paint('DONE', GREEN, BOLD)}     {text}")

    def verdict(self, ok: bool, text: str) -> None:
        tag = paint("PASS", GREEN, BOLD) if ok else paint("FAIL", RED, BOLD)
        self._emit(f"  {tag}     {text}")

    def takeaway(self, lines: list[str]) -> None:
        self._emit()
        self._emit(paint("  TAKEAWAY", MAGENTA, BOLD))
        for line in lines:
            self._emit(paint(f"  * {line}", MAGENTA))
        self._emit()
