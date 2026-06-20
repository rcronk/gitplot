"""Pytest fixtures for gitplot tests.

RepoTools builds temporary git repos for use in functional and structural tests.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


class RepoTools:
    """Builds a temporary git repository for use in tests."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._run(["git", "init", "-b", "main"])
        self._run(["git", "config", "user.email", "test@gitplot.test"])
        self._run(["git", "config", "user.name", "GitPlot Test"])

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def write(self, filename: str, content: str = "content") -> Path:
        """Create or overwrite a file in the repo."""
        fpath = self.path / filename
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return fpath

    def append(self, filename: str, extra: str = " modified") -> Path:
        """Append text to an existing file."""
        fpath = self.path / filename
        fpath.write_text(fpath.read_text(encoding="utf-8") + extra, encoding="utf-8")
        return fpath

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def add(self, *paths: str) -> None:
        args = list(paths) or ["-A"]
        self._run(["git", "add"] + args)

    def commit(self, message: str = "commit", files: list[str] | None = None) -> str:
        """Stage all or specific files and commit; return the commit hexsha."""
        if files:
            self.add(*files)
        else:
            self.add()
        self._run(["git", "commit", "-m", message])
        return self._run(["git", "rev-parse", "HEAD"])

    def checkout(self, ref: str, new: bool = False) -> None:
        cmd = ["git", "checkout"]
        if new:
            cmd.append("-b")
        cmd.append(ref)
        self._run(cmd)

    def merge(self, branch: str, no_ff: bool = True) -> None:
        msg = f"Merge branch '{branch}'"
        cmd = ["git", "merge", branch, "-m", msg]
        if no_ff:
            cmd.append("--no-ff")
        self._run(cmd)

    def tag(self, name: str, annotated: bool = False, message: str = "tag") -> None:
        if annotated:
            self._run(["git", "tag", "-a", name, "-m", message])
        else:
            self._run(["git", "tag", name])

    def detach(self, ref: str = "HEAD") -> None:
        """Detach HEAD at ref."""
        self._run(["git", "checkout", "--detach", ref])

    def current_branch(self) -> str:
        return self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    def rev_parse(self, ref: str) -> str:
        return self._run(["git", "rev-parse", ref])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, cmd: list[str]) -> str:
        return subprocess.check_output(
            cmd, cwd=self.path, stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace").strip()


@pytest.fixture
def repo(tmp_path: Path) -> RepoTools:
    """An empty, freshly initialised git repo."""
    return RepoTools(tmp_path)


# ---------------------------------------------------------------------------
# Structural assertion helpers (importable from conftest)
# ---------------------------------------------------------------------------

def node_in(source: str, node_id: str) -> bool:
    """Return True if a node with node_id appears in the DOT source."""
    return f'"{node_id}"' in source or f" {node_id} " in source or f"\t{node_id} " in source


def edge_in(source: str, from_id: str, to_id: str) -> bool:
    """Return True if an edge from_id → to_id appears in the DOT source."""
    patterns = [
        f'"{from_id}" -> "{to_id}"',
        f'"{from_id}" -> {to_id}',
        f'{from_id} -> "{to_id}"',
        f'{from_id} -> {to_id}',
    ]
    return any(p in source for p in patterns)
