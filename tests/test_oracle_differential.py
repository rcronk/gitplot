"""Differential tests: visigit's graphs vs an independent git-data oracle.

For each repo we compare visigit's output (GitPython traversal + builder walk)
against ``git_oracle`` (pure git-plumbing, a different algorithm).  They must
agree exactly.  This catches builder AND repo.py bugs on arbitrary repos --
including randomly generated ones -- without hand-enumerating expected sets.

  * normal  -- works on any repo with >=1 commit (clean or dirty; normal mode
    shows no index boxes).  Includes boring-run collapse.
  * verbose -- full object graph; needs a CLEAN working tree (no index boxes).
  * branch  -- topology is a visigit-specific presentation, so we check
    independent INVARIANTS (fork nodes are real merge-bases) rather than an
    exact reconstruction.

``assert_matches_git`` is the reusable, opt-in helper any test can call.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

import pytest

from . import git_oracle
from .conftest import RepoTools
from .test_lessons_full import assert_branch_invariants, assert_matches_git

__all__ = ["assert_branch_invariants", "assert_matches_git"]


# ---------------------------------------------------------------------------
# Scenario builders -- each builds a repo exercising a different feature.
# CLEAN scenarios end with a clean working tree (eligible for verbose).
# DIRTY scenarios leave an in-progress/unmerged state (normal mode only).
# ---------------------------------------------------------------------------


def _linear(r: RepoTools) -> None:
    for i in range(6):  # enough for a boring run to collapse in normal mode
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
    for f in ("a", "b", "c"):
        r.write(f"{f}.txt")
        r.commit(f)
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


def _merge_conflict(r: RepoTools) -> None:
    r.write("f.txt", "base")
    r.commit("base")
    r.checkout("feature", new=True)
    r.write("f.txt", "feature")
    r.commit("feature change")
    r.checkout("main")
    r.write("f.txt", "main")
    r.commit("main change")
    try:
        r._run(["git", "merge", "feature"])
    except subprocess.CalledProcessError:
        pass  # conflict -> MERGE_HEAD, dirty index


def _cherry_pick_conflict(r: RepoTools) -> None:
    r.write("f.txt", "v1")
    r.commit("init")
    r.checkout("feature", new=True)
    r.write("f.txt", "feature")
    feat = r.commit("feature change")
    r.checkout("main")
    r.write("f.txt", "main")
    r.commit("main diverges")
    try:
        r._run(["git", "cherry-pick", feat])
    except subprocess.CalledProcessError:
        pass  # conflict -> CHERRY_PICK_HEAD, dirty index


CLEAN_SCENARIOS = {
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

DIRTY_SCENARIOS = {
    "merge_conflict": _merge_conflict,
    "cherry_pick_conflict": _cherry_pick_conflict,
}

MULTI_BRANCH_SCENARIOS = ["branched", "no_ff_merge", "ff_merge", "rebase", "cherry_pick"]


# ---------------------------------------------------------------------------
# Fixed-scenario differential tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(CLEAN_SCENARIOS))
def test_verbose_oracle_clean_scenarios(name: str, repo: RepoTools) -> None:
    CLEAN_SCENARIOS[name](repo)
    assert_matches_git(str(repo.path), "verbose")


@pytest.mark.parametrize("name", list(CLEAN_SCENARIOS) + list(DIRTY_SCENARIOS))
def test_normal_oracle_all_scenarios(name: str, repo: RepoTools) -> None:
    {**CLEAN_SCENARIOS, **DIRTY_SCENARIOS}[name](repo)
    assert_matches_git(str(repo.path), "normal")


@pytest.mark.parametrize("name", MULTI_BRANCH_SCENARIOS)
def test_branch_invariants_scenarios(name: str, repo: RepoTools) -> None:
    CLEAN_SCENARIOS[name](repo)
    assert_branch_invariants(str(repo.path))


# ---------------------------------------------------------------------------
# Randomly generated repos -- property-based differential check.
#
# Each commit writes a UNIQUE file, so merges never conflict and the tree ends
# clean.  Exercises commits, branches, switches, no-ff merges, tags, and
# reset --hard (ORIG_HEAD) in random combinations.  Seeds are fixed for
# reproducibility; a failure prints the seed via the parametrize id.
# ---------------------------------------------------------------------------


def _random_repo(r: RepoTools, seed: int, steps: int = 30) -> None:
    rng = random.Random(seed)
    branches = ["main"]
    counter = 0

    def commit_unique() -> None:
        nonlocal counter
        r.write(f"file_{counter}.txt", f"content {counter}")
        r.commit(f"commit {counter}")
        counter += 1

    commit_unique()
    for _ in range(steps):
        op = rng.choice(["commit", "commit", "commit", "branch", "switch", "merge", "tag", "reset"])
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
                try:
                    r.merge(rng.choice(others), no_ff=True)  # unique files -> no conflicts
                except subprocess.CalledProcessError:
                    pass
        elif op == "tag":
            r.tag(
                f"tag{counter}_{rng.randint(0, 999)}",
                annotated=rng.choice([True, False]),
                message="m",
            )
        elif op == "reset":
            try:
                r._run(["git", "reset", "--hard", "HEAD~1"])  # stays clean; writes ORIG_HEAD
            except subprocess.CalledProcessError:
                pass
    if not git_oracle.working_tree_clean(str(r.path)):
        r._run(["git", "add", "-A"])
        r._run(["git", "commit", "-m", "final", "--allow-empty"])


@pytest.mark.parametrize("mode", ["normal", "verbose"])
@pytest.mark.parametrize("seed", range(20))
def test_oracle_matches_visigit_for_random_repo(mode: str, seed: int, tmp_path: Path) -> None:
    r = RepoTools(tmp_path)
    _random_repo(r, seed)
    assert_matches_git(str(r.path), mode)


@pytest.mark.parametrize("seed", range(20))
def test_branch_invariants_for_random_repo(seed: int, tmp_path: Path) -> None:
    r = RepoTools(tmp_path)
    _random_repo(r, seed)
    assert_branch_invariants(str(r.path))


# ---------------------------------------------------------------------------
# Bare repositories -- e.g. an "origin" on the same machine, visualised in its
# own monitor session alongside the working clone.  A bare repo has refs +
# objects but no working tree, so it renders as a commit graph with no index
# boxes.  These confirm visigit + the oracle agree on bare repos.
# ---------------------------------------------------------------------------


def _bare_clone_of(r: RepoTools) -> str:
    bare = r.path.parent / (r.path.name + ".git")
    subprocess.check_call(
        ["git", "clone", "--bare", str(r.path), str(bare)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return str(bare)


@pytest.mark.parametrize("name", ["linear", "branched", "no_ff_merge", "nested_dirs", "tags"])
def test_bare_repo_matches_oracle(name: str, repo: RepoTools) -> None:
    CLEAN_SCENARIOS[name](repo)
    bare = _bare_clone_of(repo)
    assert git_oracle.is_bare(bare)
    assert_matches_git(bare, "normal")
    assert_matches_git(bare, "verbose")  # bare has no working tree -> trivially clean
    if len(git_oracle.local_branches(bare)) >= 2:
        assert_branch_invariants(bare)


def test_empty_bare_repo_shows_empty_message(tmp_path: Path) -> None:
    """A freshly `git init --bare` origin (no commits) shows the empty-repo
    message -- it is a valid repo, not 'No git repo found'."""
    from visigit.repo import GitRepo

    from .test_lessons_full import full_graph

    bare = tmp_path / "origin.git"
    subprocess.check_call(
        ["git", "init", "--bare", "-b", "main", str(bare)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    gr = GitRepo(str(bare))
    assert gr.valid and gr.is_bare
    nodes, edges, _ = full_graph(str(bare), mode="normal")
    assert nodes == {"empty-repo"}
    assert edges == set()
