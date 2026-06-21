"""End-to-end integration tests: comprehensive git scenarios in all three render modes.

One module-scoped fixture (complex_e2e_repo) builds a real git repo that exercises
every significant scenario in one place.  Two smaller isolated fixtures cover the
edge cases that require a unique repository state: detached HEAD and shallow clone.

DeterministicRepoTools stamps every commit with a fixed, incrementing timestamp so
that commit SHAs are identical across test runs, which keeps golden files stable.

Scenarios covered
-----------------
complex_e2e_repo:
  - main branch with lightweight tag v0.1
  - develop branch with no-ff merge of feature/alpha + annotated tag v1.0
  - feature/alpha (merged, branch still exists)
  - feature/beta  (open, not merged)
  - boring-commit collapse: two boring commits on main, two on develop
  - FETCH_HEAD pointing to the initial commit
  - stash entry (one stash@{0})
  - working tree: staged file, unstaged modification, untracked file (verbose)

detached_head_repo:
  - HEAD detached at the first commit

shallow_clone_repo:
  - origin with 5 commits; clone at depth 2
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import graphviz
import pytest

from gitplot.builder import GraphBuilder
from gitplot.mermaid import dot_to_mermaid
from gitplot.repo import GitRepo

from .conftest import RepoTools, compare_golden, edge_in, node_in

# ---------------------------------------------------------------------------
# Deterministic repo builder
# ---------------------------------------------------------------------------


class DeterministicRepoTools(RepoTools):
    """RepoTools that stamps commits with a fixed, incrementing date.

    Makes commit SHAs reproducible across test runs so golden files stay stable.
    Each commit/merge/annotated-tag increments the internal sequence counter so
    timestamps are unique and monotonically increasing.
    """

    def __init__(self, path: Path) -> None:
        self._seq = 0
        super().__init__(path)

    # ------------------------------------------------------------------
    # Timestamp helpers
    # ------------------------------------------------------------------

    def _ts(self) -> str:
        s = self._seq * 60  # 1-minute gaps between operations
        return f"2000-01-01 {s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d} +0000"

    def _det_env(self) -> dict[str, str]:
        ts = self._ts()
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = ts
        env["GIT_COMMITTER_DATE"] = ts
        return env

    # ------------------------------------------------------------------
    # Overrides that create git objects
    # ------------------------------------------------------------------

    def commit(self, message: str = "commit", files: list[str] | None = None) -> str:
        if files:
            self.add(*files)
        else:
            self.add()
        subprocess.check_output(
            ["git", "commit", "-m", message],
            cwd=self.path,
            stderr=subprocess.DEVNULL,
            env=self._det_env(),
        )
        self._seq += 1
        return self._run(["git", "rev-parse", "HEAD"])

    def merge(self, branch: str, no_ff: bool = True) -> None:
        msg = f"Merge branch '{branch}'"
        cmd = ["git", "merge", branch, "-m", msg]
        if no_ff:
            cmd.append("--no-ff")
        subprocess.check_output(cmd, cwd=self.path, stderr=subprocess.DEVNULL, env=self._det_env())
        self._seq += 1

    def tag(self, name: str, annotated: bool = False, message: str = "tag") -> None:
        if annotated:
            subprocess.check_output(
                ["git", "tag", "-a", name, "-m", message],
                cwd=self.path,
                stderr=subprocess.DEVNULL,
                env=self._det_env(),
            )
            self._seq += 1
        else:
            self._run(["git", "tag", name])

    def stash(self, message: str = "wip") -> None:
        """Stage all pending index changes and stash them deterministically."""
        subprocess.check_output(
            ["git", "stash", "push", "-m", message],
            cwd=self.path,
            stderr=subprocess.DEVNULL,
            env=self._det_env(),
        )
        self._seq += 1


# ---------------------------------------------------------------------------
# Build helper
# ---------------------------------------------------------------------------


def _build(path: Path, mode: str, **kwargs) -> graphviz.Digraph:
    repo = GitRepo(str(path))
    include_trees = mode == "verbose"
    graph = repo.build_graph(include_trees=include_trees)
    index_state = repo.get_index_state() if mode == "verbose" else None
    branch_topo = repo.get_branch_topology() if mode == "branch" else None
    builder = GraphBuilder(mode=mode, **kwargs)
    return builder.build(graph, index_state=index_state, branch_topology=branch_topo)


# ---------------------------------------------------------------------------
# Complex E2E repo fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def complex_e2e_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a git repo that covers every significant scenario in one place.

    Commit topology
    ---------------
    C1   initial commit        ← main, v0.1 (lightweight tag)
    C2   boring 1
    C3   boring 2              C2+C3 collapse in normal mode
    C4   develop: start        ← develop branches from C3
    C5   alpha: first commit   ← feature/alpha branches from C4
    C6   alpha: second commit  ← feature/alpha tip
    CM   Merge feature/alpha   (no-ff, parents: C4 + C6) ← v1.0 (annotated)
    C7   boring dev 1
    C8   boring dev 2          C7+C8 collapse in normal mode
    C9   develop: milestone
    C10  beta: first commit    ← feature/beta branches from C9
    C11  beta: second commit   ← feature/beta tip
    C12  develop: latest       ← develop tip, HEAD

    Extra state
    -----------
    FETCH_HEAD → C1
    stash@{0}  → staged change on C12
    Working tree: scratch.txt (untracked), develop.txt modified (unstaged),
                  index_file.txt staged (new file)
    """
    base = tmp_path_factory.mktemp("e2e_repo")
    r = DeterministicRepoTools(base)

    # main: initial commit + 2 boring commits
    r.write("README.md", "# gitplot\n")
    r.commit("initial commit")
    r.tag("v0.1")

    r.write("file1.txt", "alpha content\n")
    r.commit("boring 1")

    r.write("file2.txt", "beta content\n")
    r.commit("boring 2")

    # develop: branch from main, add a commit
    r.checkout("develop", new=True)
    r.write("develop.txt", "develop start\n")
    r.commit("develop: start")

    # feature/alpha: 2 commits, merged no-ff into develop
    r.checkout("feature/alpha", new=True)
    r.write("alpha.txt", "alpha v1\n")
    r.commit("alpha: first commit")
    r.write("alpha.txt", "alpha v2\n")
    r.commit("alpha: second commit")

    r.checkout("develop")
    r.merge("feature/alpha", no_ff=True)
    r.tag("v1.0", annotated=True, message="Release 1.0")

    # 2 boring commits on develop
    r.write("develop.txt", "boring dev 1\n")
    r.commit("boring dev 1")
    r.write("develop.txt", "boring dev 2\n")
    r.commit("boring dev 2")

    # develop milestone
    r.write("develop.txt", "milestone\n")
    r.commit("develop: milestone")

    # feature/beta: 2 commits, NOT merged
    r.checkout("feature/beta", new=True)
    r.write("beta.txt", "beta v1\n")
    r.commit("beta: first commit")
    r.write("beta.txt", "beta v2\n")
    r.commit("beta: second commit")

    # final develop commit
    r.checkout("develop")
    r.write("develop.txt", "latest\n")
    r.commit("develop: latest")

    # FETCH_HEAD: point at the initial commit (v0.1 tag)
    sha_v01 = r.rev_parse("v0.1")
    (base / ".git" / "FETCH_HEAD").write_text(
        f"{sha_v01}\t\tbranch 'main' of ../origin\n",
        encoding="utf-8",
    )

    # Stash: stage a modification then stash it
    r.write("develop.txt", "wip change\n")
    r.add("develop.txt")
    r.stash("wip: experiment")

    # Working tree state for verbose-mode tests
    (base / "scratch.txt").write_text("not tracked\n", encoding="utf-8")
    (base / "develop.txt").write_text("unstaged modification\n", encoding="utf-8")
    (base / "index_file.txt").write_text("staged content\n", encoding="utf-8")
    subprocess.check_output(["git", "add", "index_file.txt"], cwd=base, stderr=subprocess.DEVNULL)

    return base


# ---------------------------------------------------------------------------
# Detached HEAD fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def detached_head_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two commits; HEAD detached at the first."""
    base = tmp_path_factory.mktemp("detached_repo")
    r = DeterministicRepoTools(base)
    r.write("a.txt", "hello\n")
    r.commit("first")
    r.write("b.txt", "world\n")
    r.commit("second")
    sha_first = r.rev_parse("HEAD~1")
    r.detach(sha_first)
    return base


# ---------------------------------------------------------------------------
# Shallow clone fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def shallow_clone_repo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Origin with 5 commits; clone at depth 2."""
    origin = tmp_path_factory.mktemp("shallow_origin")
    r = DeterministicRepoTools(origin)
    for i in range(1, 6):
        r.write("file.txt", f"v{i}\n")
        r.commit(f"commit {i}")

    clone_path = tmp_path_factory.mktemp("shallow_clone")
    # Use file:// protocol so git uses the transfer protocol and respects --depth,
    # instead of the default local optimisation that copies all objects via hardlinks.
    # Path.as_uri() produces the correct file:/// form on both Linux and Windows.
    subprocess.check_output(
        ["git", "clone", "--depth", "2", origin.as_uri(), str(clone_path)],
        stderr=subprocess.DEVNULL,
    )
    return origin, clone_path


# ============================================================================
# Normal mode — complex_e2e_repo
# ============================================================================


class TestNormalMode:
    def test_dot_source_matches_golden(self, complex_e2e_repo: Path, request) -> None:
        dg = _build(complex_e2e_repo, "normal")
        compare_golden(request, "complex_normal.dot", dg.source)

    def test_mermaid_matches_golden(self, complex_e2e_repo: Path, request) -> None:
        dg = _build(complex_e2e_repo, "normal")
        compare_golden(request, "complex_normal.mermaid", dot_to_mermaid(dg.source))

    def test_boring_commits_collapse(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "normal").source
        # At least one "(N)" summary node must be present
        assert "(2)" in src, "Boring run of 2 commits must produce a summary node"

    def test_head_points_to_develop(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "normal").source
        assert node_in(src, "HEAD")
        assert "develop" in src

    def test_lightweight_tag_appears(self, complex_e2e_repo: Path) -> None:
        assert "v0.1" in _build(complex_e2e_repo, "normal").source

    def test_annotated_tag_has_tag_object_node(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "normal").source
        assert "v1.0" in src
        # Annotated tag produces a ref→tag-object→commit chain; there must be
        # at least two edges out of the v1.0 ref (one to tag object, one to commit)
        assert src.count('"refs/tags/v1.0"') >= 2

    def test_fetch_head_appears(self, complex_e2e_repo: Path) -> None:
        assert "FETCH_HEAD" in _build(complex_e2e_repo, "normal").source

    def test_feature_alpha_branch_appears(self, complex_e2e_repo: Path) -> None:
        assert "feature/alpha" in _build(complex_e2e_repo, "normal").source

    def test_feature_beta_branch_appears(self, complex_e2e_repo: Path) -> None:
        assert "feature/beta" in _build(complex_e2e_repo, "normal").source

    def test_merge_commit_two_parents_in_graph(self, complex_e2e_repo: Path) -> None:
        repo = GitRepo(str(complex_e2e_repo))
        graph = repo.build_graph()
        merge_commits = [sha for sha, cd in graph.commits.items() if len(cd.parents) == 2]
        assert len(merge_commits) >= 1, "Expected at least one 2-parent merge commit"

    def test_main_branch_appears(self, complex_e2e_repo: Path) -> None:
        assert "main" in _build(complex_e2e_repo, "normal").source


# ============================================================================
# Verbose mode — complex_e2e_repo
# ============================================================================


class TestVerboseMode:
    def test_dot_source_matches_golden(self, complex_e2e_repo: Path, request) -> None:
        dg = _build(complex_e2e_repo, "verbose")
        compare_golden(request, "complex_verbose.dot", dg.source)

    def test_mermaid_matches_golden(self, complex_e2e_repo: Path, request) -> None:
        dg = _build(complex_e2e_repo, "verbose")
        compare_golden(request, "complex_verbose.mermaid", dot_to_mermaid(dg.source))

    def test_tree_nodes_appear(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "verbose").source
        # Verbose mode adds tree objects; the edge label "tree" must appear
        assert "label=tree" in src or 'label="tree"' in src

    def test_blob_name_appears(self, complex_e2e_repo: Path) -> None:
        # README.md blob should be visible
        assert "README.md" in _build(complex_e2e_repo, "verbose").source

    def test_stash_appears(self, complex_e2e_repo: Path) -> None:
        assert "stash" in _build(complex_e2e_repo, "verbose").source

    def test_staged_changes_appear(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "verbose").source
        assert "Staged Changes" in src
        assert "index_file.txt" in src

    def test_unstaged_changes_appear(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "verbose").source
        assert "Unstaged Changes" in src
        assert "develop.txt" in src

    def test_untracked_files_appear(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "verbose").source
        assert "Untracked" in src
        assert "scratch.txt" in src

    def test_fetch_head_appears(self, complex_e2e_repo: Path) -> None:
        assert "FETCH_HEAD" in _build(complex_e2e_repo, "verbose").source

    def test_annotated_tag_shows_tag_object(self, complex_e2e_repo: Path) -> None:
        assert "v1.0" in _build(complex_e2e_repo, "verbose").source


# ============================================================================
# Branch mode — complex_e2e_repo
# ============================================================================


class TestBranchMode:
    def test_dot_source_matches_golden(self, complex_e2e_repo: Path, request) -> None:
        dg = _build(complex_e2e_repo, "branch")
        compare_golden(request, "complex_branch.dot", dg.source)

    def test_mermaid_matches_golden(self, complex_e2e_repo: Path, request) -> None:
        dg = _build(complex_e2e_repo, "branch")
        compare_golden(request, "complex_branch.mermaid", dot_to_mermaid(dg.source))

    def test_all_dev_branches_appear(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "branch").source
        for name in ("main", "develop", "feature/alpha", "feature/beta"):
            assert name in src, f"Branch {name!r} missing from branch-mode output"

    def test_tags_appear(self, complex_e2e_repo: Path) -> None:
        src = _build(complex_e2e_repo, "branch").source
        assert "v0.1" in src
        assert "v1.0" in src

    def test_stash_appears(self, complex_e2e_repo: Path) -> None:
        assert "stash" in _build(complex_e2e_repo, "branch").source

    def test_fetch_head_appears(self, complex_e2e_repo: Path) -> None:
        assert "FETCH_HEAD" in _build(complex_e2e_repo, "branch").source

    def test_fork_commit_nodes_exist(self, complex_e2e_repo: Path) -> None:
        assert "fork" in _build(complex_e2e_repo, "branch").source

    def test_major_branches_are_connected(self, complex_e2e_repo: Path) -> None:
        """Every major branch must appear on at least one edge in the topology."""
        repo = GitRepo(str(complex_e2e_repo))
        topo = repo.get_branch_topology()
        touched = {e.from_id for e in topo.edges} | {e.to_id for e in topo.edges}
        fork_hexshas = {f.hexsha for f in topo.fork_commits}
        touched |= fork_hexshas
        for name in ("main", "develop", "feature/alpha", "feature/beta"):
            assert name in touched, f"Branch {name!r} is disconnected in branch topology"


# ============================================================================
# Detached HEAD
# ============================================================================


class TestDetachedHead:
    def test_normal_head_node_exists(self, detached_head_repo: Path) -> None:
        assert node_in(_build(detached_head_repo, "normal").source, "HEAD")

    def test_normal_head_edge_goes_to_commit_not_branch(self, detached_head_repo: Path) -> None:
        # When HEAD is detached the builder emits HEAD → <commit_sha> directly,
        # not HEAD → refs/heads/<branch>.  The branch ref still exists as its own
        # node (main is still there), but HEAD's edge must bypass it.
        src = _build(detached_head_repo, "normal").source
        assert node_in(src, "HEAD")
        assert not edge_in(src, "HEAD", "refs/heads/main")

    def test_normal_dot_matches_golden(self, detached_head_repo: Path, request) -> None:
        dg = _build(detached_head_repo, "normal")
        compare_golden(request, "detached_head_normal.dot", dg.source)

    def test_normal_mermaid_matches_golden(self, detached_head_repo: Path, request) -> None:
        dg = _build(detached_head_repo, "normal")
        compare_golden(request, "detached_head_normal.mermaid", dot_to_mermaid(dg.source))

    def test_branch_mode_shows_detached_label(self, detached_head_repo: Path) -> None:
        src = _build(detached_head_repo, "branch").source
        assert "detached" in src.lower()

    def test_branch_dot_matches_golden(self, detached_head_repo: Path, request) -> None:
        dg = _build(detached_head_repo, "branch")
        compare_golden(request, "detached_head_branch.dot", dg.source)

    def test_branch_mermaid_matches_golden(self, detached_head_repo: Path, request) -> None:
        dg = _build(detached_head_repo, "branch")
        compare_golden(request, "detached_head_branch.mermaid", dot_to_mermaid(dg.source))

    def test_verbose_dot_matches_golden(self, detached_head_repo: Path, request) -> None:
        dg = _build(detached_head_repo, "verbose")
        compare_golden(request, "detached_head_verbose.dot", dg.source)

    def test_verbose_mermaid_matches_golden(self, detached_head_repo: Path, request) -> None:
        dg = _build(detached_head_repo, "verbose")
        compare_golden(request, "detached_head_verbose.mermaid", dot_to_mermaid(dg.source))


# ============================================================================
# Shallow clone
# ============================================================================


class TestShallowClone:
    def test_no_phantom_nodes(self, shallow_clone_repo: tuple[Path, Path]) -> None:
        _, clone_path = shallow_clone_repo
        src = _build(clone_path, "normal").source
        assert "No git repo found" not in src

    def test_exactly_two_commits_visible(self, shallow_clone_repo: tuple[Path, Path]) -> None:
        _, clone_path = shallow_clone_repo
        repo = GitRepo(str(clone_path))
        graph = repo.build_graph()
        assert len(graph.commits) == 2, (
            f"Expected 2 commits in depth-2 shallow clone, got {len(graph.commits)}"
        )

    def test_no_dangling_parent_edges(self, shallow_clone_repo: tuple[Path, Path]) -> None:
        _, clone_path = shallow_clone_repo
        repo = GitRepo(str(clone_path))
        graph = repo.build_graph()
        for sha, cd in graph.commits.items():
            for parent in cd.parents:
                assert parent in graph.commits, (
                    f"Commit {sha[:8]} has parent {parent[:8]} not in graph — "
                    "dangling edge would produce a phantom node"
                )

    def test_normal_dot_matches_golden(
        self, shallow_clone_repo: tuple[Path, Path], request
    ) -> None:
        _, clone_path = shallow_clone_repo
        compare_golden(request, "shallow_clone_normal.dot", _build(clone_path, "normal").source)

    def test_normal_mermaid_matches_golden(
        self, shallow_clone_repo: tuple[Path, Path], request
    ) -> None:
        _, clone_path = shallow_clone_repo
        dg = _build(clone_path, "normal")
        compare_golden(request, "shallow_clone_normal.mermaid", dot_to_mermaid(dg.source))

    def test_branch_mode_no_crash(self, shallow_clone_repo: tuple[Path, Path]) -> None:
        _, clone_path = shallow_clone_repo
        src = _build(clone_path, "branch").source
        assert "No git repo found" not in src

    def test_branch_dot_matches_golden(
        self, shallow_clone_repo: tuple[Path, Path], request
    ) -> None:
        _, clone_path = shallow_clone_repo
        compare_golden(request, "shallow_clone_branch.dot", _build(clone_path, "branch").source)

    def test_branch_mermaid_matches_golden(
        self, shallow_clone_repo: tuple[Path, Path], request
    ) -> None:
        _, clone_path = shallow_clone_repo
        dg = _build(clone_path, "branch")
        compare_golden(request, "shallow_clone_branch.mermaid", dot_to_mermaid(dg.source))

    def test_verbose_dot_matches_golden(
        self, shallow_clone_repo: tuple[Path, Path], request
    ) -> None:
        _, clone_path = shallow_clone_repo
        compare_golden(request, "shallow_clone_verbose.dot", _build(clone_path, "verbose").source)

    def test_verbose_mermaid_matches_golden(
        self, shallow_clone_repo: tuple[Path, Path], request
    ) -> None:
        _, clone_path = shallow_clone_repo
        dg = _build(clone_path, "verbose")
        compare_golden(request, "shallow_clone_verbose.mermaid", dot_to_mermaid(dg.source))
