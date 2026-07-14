"""Real tools over a sandboxed workspace directory.

Every call actually touches disk or spawns a process — nothing here is
narrated. This is what "fresh context, persistent files" means concretely:
the model never carries conversation history between ticks, only whatever
it chooses to read back off disk through these tools.
"""

import os
import re
import subprocess
from pathlib import Path


class Toolbox:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel: str) -> Path:
        path = (self.workspace / rel).resolve()
        if not str(path).startswith(str(self.workspace.resolve())):
            raise PermissionError(f"path escapes workspace: {rel}")
        return path

    def call(self, name: str, **kwargs) -> str:
        return getattr(self, name)(**kwargs)

    # -- file system ------------------------------------------------------

    def ls(self, path: str = ".") -> str:
        target = self._resolve(path)
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return "\n".join(entries) if entries else "(empty)"

    def read(self, path: str) -> str:
        target = self._resolve(path)
        if not target.exists():
            return f"ERROR: {path} does not exist"
        return target.read_text()

    def write(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"wrote {len(content)} bytes to {path}"

    def append(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a") as f:
            f.write(content)
        return f"appended {len(content)} bytes to {path}"

    def edit(self, path: str, old: str, new: str) -> str:
        target = self._resolve(path)
        text = target.read_text()
        if old not in text:
            return f"ERROR: string not found in {path}"
        target.write_text(text.replace(old, new, 1))
        return f"edited {path} (1 replacement)"

    def grep(self, pattern: str, path: str = ".") -> str:
        root = self._resolve(path)
        hits = []
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for file in files:
            if not file.is_file():
                continue
            try:
                for i, line in enumerate(file.read_text().splitlines(), 1):
                    if re.search(pattern, line):
                        rel = file.relative_to(self.workspace)
                        hits.append(f"{rel}:{i}: {line.strip()}")
            except UnicodeDecodeError:
                continue
        return "\n".join(hits) if hits else f"no matches for /{pattern}/"

    # -- shell execution ---------------------------------------------------

    def bash(self, cmd: str, timeout: int = 30) -> str:
        # Rapid edit-then-rerun within the same wall-clock second can outrun
        # Python's mtime-based .pyc cache invalidation; disable it so every
        # invocation always reflects the file as just written.
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run(
            cmd, shell=True, cwd=self.workspace, timeout=timeout,
            capture_output=True, text=True, env=env,
        )
        out = (proc.stdout + proc.stderr).strip()
        return f"exit={proc.returncode}\n{out}" if out else f"exit={proc.returncode}"
