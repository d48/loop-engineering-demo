"""loop_harness — a small, honest harness for teaching "loop engineering".

The central object is `LoopRunner`: it repeats scripted agent turns until a
real, computed predicate says the goal is met, or a turn budget runs out.
That single mechanism is the article's own definition of the difference
between a prompt ("do this next thing") and a goal ("keep working until
this outcome is true") — every demo in this repo is that same runner
pointed at a different real task and a different real predicate.

The "model" turns are scripted (deterministic, no API key needed) so the
demos are reproducible on stage, but the tasks, files, test runs, and
predicate checks around them are all real.
"""

from .loop import LoopRunner
from .model import Action, ScriptedModel
from .tools import Toolbox
from .trace import Trace

__all__ = ["Action", "LoopRunner", "ScriptedModel", "Toolbox", "Trace"]
