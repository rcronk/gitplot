"""Differential tests: visigit's verbose graph vs an independent git-data oracle.

For each repo, we compare visigit's verbose-mode output (GitPython traversal +
builder walk) against `git_oracle.expected_verbose_graph` (pure git-plumbing,
a different algorithm).  They must agree exactly on nodes and labelled edges.

This catches builder AND repo.py bugs on arbitrary repos -- including randomly
generated ones -- without hand-enumerating expected sets per scenario.

Oracle scope (see git_oracle): a repo with >=1 commit and a CLEAN working tree
(no index boxes to model).  Each scenario/generator below ends clean.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

import pytest

from . import git_oracle
from .conftest import RepoTools
from .test_lessons_full import assert_exact, full_graph


def _check(repo_path: str) -> None:
    """Assert visigit's verbose graph equals the oracle's for this repo."""
    assert git_oracle.has_commit(repo_path), "oracle needs at least one commit"
    assert git_oracle.working_tree_clean(repo_path), (
        "oracle models a clean working tree only (no index boxes)"
    )
    exp_nodes, exp_edges = git_oracle.expected_verbose_graph(repo_path)
    nodes, edges, _ = full_graph(repo_path, mode="verbose")
    assert_exact(nodes, edges, exp_nodes, exp_edges, f"oracle diff @ {repo_path}")


# ---------------------------------------------------------------------------
# Fixed scenarios -- each builds a clean repo exercising a different feature.
# ---------------------------------------------------------------------------


def _linear(r: RepoTools) -> None:
    for i in range(4):
        r.write(f"f{i}.txt", f"v{i}")
        r.commit(f"c{i}")


def _branched(r: RepoTools) -> None:
    r.write("base.txt")
    r.commit("base")
    r.checkout("feature", new=True)
    r.write("feat.txt")
    r.commit("feat")
    r.checkout("main")
    r.write("main.txt")
    r.commit("main work")


def _no_ff_merge(r: RepoTools) -> None:
    r.write("base.txt")
    r.commit("base")
    r.checkout("feature", new=True)
    r.write("feat.txt")
    r.commit("feat")
    r.checkout("main")
    r.write("fix.txt")
    r.commit("hotfix")
    r.merge("feature", no_ff=True)


def _ff_merge(r: RepoTools) -> None:
    r.write("base.txt")
    r.commit("base")
    r.checkout("feature", new=True)
    r.write("feat.txt")
    r.commit("feat")
    r.checkout("main")
    r._run(["git", "merge", "feature"])


def _reset_hard(r: RepoTools) -> None:
    r.write("a.txt")
    r.commit("a")
    r.write("b.txt")
    r.commit("b")
    r.write("c.txt")
    r.commit("c")
    r._run(["git", "reset", "--hard", "HEAD~1"])  # writes ORIG_HEAD


def _rebase(r: RepoTools) -> None:
    r.write("base.txt")
    r.commit("base")
    r.checkout("feature", new=True)
    r.write("feat.txt")
    r.commit("feat")
    r.checkout("main")
    r.write("main.txt")
    r.commit("main work")
    r.checkout("feature")
    r._run(["git", "rebase", "main"])  # writes ORIG_HEAD


def _cherry_pick(r: RepoTools) -> None:
    r.write("base.txt")
    r.commit("base")
    r.checkout("feature", new=True)
    r.write("gem.txt", "gem")
    gem = r.commit("gem")
    r.checkout("main")
    r.write("mw.txt")
    r.commit("main work")
    r._run(["git", "cherry-pick", gem])


def _tags(r: RepoTools) -> None:
    r.write("a.txt")
    r.commit("c")
    r.tag("v1.0", annotated=False)
    r.tag("v2.0", annotated=True, message="rel")


def _nested_dirs(r: RepoTools) -> None:
    r.write("README.md", "# r")
    r.write("src/core.py", "x")
    r.write("src/util/helper.py", "y")
    r.write("docs/guide.md", "g")
    r.commit("nested")


def _stash(r: RepoTools) -> None:
    r.write("a.txt", "original")
    r.commit("base")
    r.write("a.txt", "modified")
    r._run(["git", "add", "-A"])
    r._run(["git", "stash"])  # leaves a clean working tree


def _detached(r: RepoTools) -> None:
    r.write("a.txt")
    c1 = r.commit("a")
    r.write("b.txt")
    r.commit("b")
    r.detach(c1)


def _submodule(r: RepoTools) -> None:
    sub = r.path.parent / (r.path.name + "_sub")
    subprocess.check_call(
        ["git", "init", "-b", "main", str(sub)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for cfg in (["user.email", "s@s"], ["user.name", "S"]):
        subprocess.check_call(["git", "config", *cfg], cwd=sub, stderr=subprocess.DEVNULL)
    (sub / "sub.txt").write_text("s")
    subprocess.check_call(["git", "add", "-A"], cwd=sub, stderr=subprocess.DEVNULL)
    subprocess.check_call(["git", "commit", "-m", "subinit"], cwd=sub, stderr=subprocess.DEVNULL)
    r.write("main.txt")
    r._run(["git", "add", "main.txt"])
    r._run(["git", "-c", "protocol.file.allow=always", "submodule", "add", sub.as_posix(), "lib"])
    r.commit("add submodule")


def _remote_push(r: RepoTools) -> None:
    remote = r.path.parent / (r.path.name + "_remote.git")
    subprocess.check_call(
        ["git", "init", "--bare", "-b", "main", str(remote)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    r.write("a.txt")
    r.commit("c1")
    r._run(["git", "remote", "add", "origin", str(remote)])
    r._run(["git", "push", "-u", "origin", "main"])
    r.write("b.txt")
    r.commit("c2")  # local ahead of origin/main


SCENARIOS = {
    "linear": _linear,
    "branched": _branched,
    "no_ff_merge": _no_ff_merge,
    "ff_merge": _ff_merge,
    "reset_hard": _reset_hard,
    "rebase": _rebase,
    "cherry_pick": _cherry_pick,
    "tags": _tags,
    "nested_dirs": _nested_dirs,
    "stash": _stash,
    "detached": _detached,
    "submodule": _submodule,
    "remote_push": _remote_push,
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_oracle_matches_visigit_for_scenario(name: str, repo: RepoTools) -> None:
    SCENARIOS[name](repo)
    _check(str(repo.path))


# ---------------------------------------------------------------------------
# Randomly generated repos -- property-based differential check.
#
# Each commit writes a UNIQUE file, so merges never conflict and the tree always
# ends clean.  Exercises commits, branches, switches, no-ff merges, tags, and
# reset --hard (ORIG_HEAD) in random combinations.  Seeds are fixed for
# reproducibility; a failure prints the seed.
# ---------------------------------------------------------------------------


def _random_repo(r: RepoTools, seed: int, steps: int = 25) -> None:
    rng = random.Random(seed)
    branches = ["main"]
    counter = 0

    def commit_unique() -> None:
        nonlocal counter
        r.write(f"file_{counter}.txt", f"content {counter}")
        r.commit(f"commit {counter}")
        counter += 1

    commit_unique()  # ensure at least one commit
    for _ in range(steps):
        op = rng.choice(["commit", "commit", "branch", "switch", "merge", "tag", "reset"])
        cur = r.current_branch()
        if op == "commit":
            commit_unique()
        elif op == "branch":
            new = f"b{counter}_{rng.randint(0, 999)}"
            if new not in branches:
                r.checkout(new, new=True)
                branches.append(new)
                commit_unique()
        elif op == "switch":
            r.checkout(rng.choice(branches))
        elif op == "merge":
            others = [b for b in branches if b != cur]
            if others:
                target = rng.choice(others)
                try:
                    r.merge(target, no_ff=True)  # unique files -> no conflicts
                except subprocess.CalledProcessError:
                    pass
        elif op == "tag":
            tname = f"tag{counter}_{rng.randint(0, 999)}"
            r.tag(tname, annotated=rng.choice([True, False]), message="m")
        elif op == "reset":
            try:
                r._run(["git", "reset", "--hard", "HEAD~1"])  # stays clean; writes ORIG_HEAD
            except subprocess.CalledProcessError:
                pass
    # Guarantee a clean tree for the oracle (commit anything left over).
    if not git_oracle.working_tree_clean(str(r.path)):
        r._run(["git", "add", "-A"])
        r._run(["git", "commit", "-m", "final", "--allow-empty"])


@pytest.mark.parametrize("seed", range(20))
def test_oracle_matches_visigit_for_random_repo(seed: int, tmp_path: Path) -> None:
    r = RepoTools(tmp_path)
    _random_repo(r, seed)
    _check(str(r.path))
