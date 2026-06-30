"""Exhaustive, full-diagram verification of every curriculum lesson step.

Where ``tests/test_lessons.py`` asserts only the *key* nodes/edges for each
lesson, this suite asserts the **complete** diagram: the exact set of nodes and
the exact set of (from, to, label) edges visigit produces for each git state in
``docs/curriculum.md``.  Both *missing* and *extra/phantom* elements fail.

Ground truth is derived by reasoning about git semantics, not by blessing the
tool's output -- so a bug that adds a stray node, draws an extra edge, or
mislabels an edge is caught here even though the partial checks would pass.

The authoritative node/edge sets are read straight off the ``GraphBuilder``
(``builder.node_ids`` and ``builder._rendered_edges``), which is exactly what
gets rendered to DOT -- no fragile DOT-source parsing.

Run with:
    pytest tests/test_lessons_full.py -v
"""

from __future__ import annotations

import pytest

from visigit.builder import GraphBuilder
from visigit.repo import GitRepo

from . import git_oracle
from .conftest import RepoTools

# An edge is identified by (from_id, to_id, label) -- labels matter for teaching
# accuracy (e.g. "HEAD" vs "branch" vs "parent" vs a filename).
Edge = tuple[str, str, str]


class _CapturingBuilder(GraphBuilder):
    """GraphBuilder that records each node's label as it is added.

    Lets tests verify node labels (e.g. the worktree '[wt: ...]' annotation, or
    that a commit SHA node is labelled 'commit' and not 'blob') without parsing
    DOT source.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.labels: dict[str, str] = {}

    def _add_node(self, dg, node_id: str, label: str, type_key: str) -> None:
        if node_id not in self._rendered_nodes:
            self.labels[node_id] = label
        super()._add_node(dg, node_id, label=label, type_key=type_key)


def build_with_labels(
    repo_path: str,
    mode: str = "normal",
    exclude_remotes: bool = False,
    **kwargs,
) -> tuple[set[str], set[Edge], dict[str, str], object]:
    """Build the diagram and return (nodes, edges, labels, RepoGraph)."""
    git_repo = GitRepo(repo_path)
    include_trees = mode == "verbose"
    graph = git_repo.build_graph(include_trees=include_trees, exclude_remotes=exclude_remotes)
    index_state = git_repo.get_index_state() if mode == "verbose" else None
    branch_topo = git_repo.get_branch_topology() if mode == "branch" else None
    builder = _CapturingBuilder(mode=mode, **kwargs)
    builder.build(graph, index_state=index_state, branch_topology=branch_topo)
    nodes = set(builder.node_ids)
    edges = set(builder._rendered_edges)
    return nodes, edges, builder.labels, graph


def full_graph(
    repo_path: str,
    mode: str = "normal",
    exclude_remotes: bool = False,
    **kwargs,
) -> tuple[set[str], set[Edge], object]:
    """Build the diagram and return (nodes, edges, RepoGraph).

    nodes -- the complete set of node IDs the builder emitted.
    edges -- the complete set of (from, to, label) triples the builder emitted.
    """
    nodes, edges, _labels, graph = build_with_labels(
        repo_path, mode=mode, exclude_remotes=exclude_remotes, **kwargs
    )
    return nodes, edges, graph


def _fmt(items) -> str:
    return "\n".join(f"    {i!r}" for i in sorted(items, key=repr)) or "    (none)"


def assert_exact(
    nodes: set[str],
    edges: set[Edge],
    expected_nodes: set[str],
    expected_edges: set[Edge],
    msg: str = "",
) -> None:
    """Assert the diagram's nodes and edges exactly equal the expected sets."""
    node_errs = []
    if nodes != expected_nodes:
        missing = expected_nodes - nodes
        extra = nodes - expected_nodes
        node_errs.append(
            f"NODE MISMATCH ({msg}):\n"
            f"  MISSING (expected, not drawn):\n{_fmt(missing)}\n"
            f"  EXTRA (drawn, not expected):\n{_fmt(extra)}"
        )
    edge_errs = []
    if edges != expected_edges:
        missing = expected_edges - edges
        extra = edges - expected_edges
        edge_errs.append(
            f"EDGE MISMATCH ({msg}):\n"
            f"  MISSING (expected, not drawn):\n{_fmt(missing)}\n"
            f"  EXTRA (drawn, not expected):\n{_fmt(extra)}"
        )
    assert not node_errs and not edge_errs, "\n".join(node_errs + edge_errs)


# ---------------------------------------------------------------------------
# Independent git-data oracle cross-checks (see tests/git_oracle.py)
# ---------------------------------------------------------------------------


def assert_matches_git(repo_path: str, mode: str, exclude_remotes: bool = False) -> None:
    """Assert visigit's ``mode`` graph equals the independent git oracle's.

    Eligibility: repo has >=1 commit; for verbose mode the working tree must be
    clean (the oracle does not model the staged/unstaged/untracked index boxes).
    Independent of the hand-derived expected sets, so if my hand expectation is
    wrong in the same way visigit is wrong, this still catches it.
    """
    assert git_oracle.has_commit(repo_path), "oracle needs at least one commit"
    if mode == "verbose":
        assert git_oracle.working_tree_clean(repo_path), (
            "verbose oracle models a clean working tree only (no index boxes)"
        )
    exp_nodes, exp_edges = git_oracle.expected_graph(repo_path, mode, exclude_remotes)
    nodes, edges, _ = full_graph(repo_path, mode=mode, exclude_remotes=exclude_remotes)
    assert_exact(nodes, edges, exp_nodes, exp_edges, f"oracle({mode}) @ {repo_path}")


def assert_branch_invariants(repo_path: str) -> None:
    """Independent branch-mode checks: every fork (SHA) node is a real merge-base
    of some ref-tip pair, and every local branch appears as a node."""
    nodes, _edges, _ = full_graph(repo_path, mode="branch")
    sha_nodes = {n for n in nodes if git_oracle._is_sha(n)}
    bogus = sha_nodes - git_oracle.all_merge_bases(repo_path)
    assert not bogus, f"branch-mode fork nodes that are NOT merge-bases of any ref pair: {bogus}"
    missing = git_oracle.local_branches(repo_path) - nodes
    assert not missing, f"local branches missing from branch-mode graph: {missing}"


@pytest.fixture(autouse=True)
def _oracle_crosscheck(repo: RepoTools):
    """After EVERY curriculum step, cross-check the final repo state against the
    independent git oracle in all eligible modes -- so no lesson diagram can be
    wrong (or my hand-derived expectation misleading) without a test failing.

    Eligibility is guarded so intentionally-partial states (empty/unborn repos,
    dirty trees for verbose) are skipped rather than failing.
    """
    yield
    path = str(repo.path)
    if not git_oracle.has_commit(path):
        return  # empty/unborn repo -- oracle not applicable
    # Normal mode works on any committed repo (clean or dirty -- no index boxes).
    assert_matches_git(path, "normal")
    # Verbose mode only when the working tree is clean.
    if git_oracle.working_tree_clean(path):
        assert_matches_git(path, "verbose")
    # Branch mode invariants whenever there is something to fork.
    if len(git_oracle.local_branches(path)) >= 2:
        assert_branch_invariants(path)


# ---------------------------------------------------------------------------
# EP 02 -- Your First Repository
#
# Mode: normal.  Lesson beats:
#   - git init / git add (pre-commit): the graph is empty -- HEAD and the branch
#     ref do not appear until the first commit "appears at once" with it.
#   - first commit: three-tier HEAD -> refs/heads/main -> commit.
#   - each new commit: a new commit node with a parent edge to the previous tip.
#   - a boring run (1 parent, 1 child, 0 refs) collapses into one summary node.
# ---------------------------------------------------------------------------


class TestEP02FirstRepoFull:
    def test_init_only_is_empty_repo_message(self, repo: RepoTools) -> None:
        """After git init (no commits): the only node is the empty-repo message.

        HEAD and refs/heads/main must NOT appear yet -- per the lesson they
        "appear at once" with the first commit.  A valid-but-empty repo must not
        be labelled 'No git repo found'.
        """
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        assert_exact(nodes, edges, {"empty-repo"}, set(), "init only")

    def test_staged_before_first_commit_normal_mode_is_empty(self, repo: RepoTools) -> None:
        """git add before the first commit (normal mode): still just the empty-repo
        message.  Staging does not create a commit, so nothing else appears."""
        repo.write("README.md", "# Hello")
        repo._run(["git", "add", "README.md"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        assert_exact(nodes, edges, {"empty-repo"}, set(), "staged pre-commit")

    def test_first_commit_three_tier(self, repo: RepoTools) -> None:
        """git commit: exactly HEAD -> refs/heads/main -> commit, nothing else."""
        repo.write("README.md", "# Hello")
        sha = repo.commit("initial")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", sha}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", sha, "branch"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "first commit")

    def test_second_commit_adds_parent_edge(self, repo: RepoTools) -> None:
        """Second commit: new node + parent edge to the first; main advances to it."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", sha1, sha2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", sha2, "branch"),
            (sha2, sha1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "second commit")

    def test_third_commit_linear_chain(self, repo: RepoTools) -> None:
        """Three commits: a fully linear chain, each pointing at its parent.

        Three commits are NOT collapsed: the middle commit is the only candidate
        for boring (the first has 0 parents, the tip has refs), and a single
        boring commit renders as a normal commit node, not a summary.
        """
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second")
        repo.write("c.txt")
        sha3 = repo.commit("third")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", sha1, sha2, sha3}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", sha3, "branch"),
            (sha3, sha2, "parent"),
            (sha2, sha1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "third commit")

    def test_boring_run_collapses_to_summary(self, repo: RepoTools) -> None:
        """Five commits: the three boring middle commits collapse into one summary node.

        Commits (oldest->newest): c0 (0 parents -> not boring), c1, c2, c3
        (each 1 parent/1 child/0 refs -> boring), c4 (has refs -> not boring).

        The walk runs newest->oldest, so the boring run accumulates as [c3, c2, c1];
        the summary node's ID is the run's first element c3 (the newest boring commit).
        Resulting graph:
            HEAD -> main -> c4 -> [summary c3] -> c0
        """
        repo.write("base.txt")
        c0 = repo.commit("c0")
        shas = [c0]
        for i in range(4):
            repo.write(f"f{i}.txt")
            shas.append(repo.commit(f"c{i + 1}"))
        c4 = shas[4]
        summary_id = shas[3]  # newest boring commit == run[0]
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", c4, summary_id, c0}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c4, "branch"),
            (c4, summary_id, "parent"),
            (summary_id, c0, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "boring collapse")


# ---------------------------------------------------------------------------
# EP 03 -- Branches Aren't Copies
#
# Mode: normal.  Lesson beats:
#   - a new branch is just a label on an existing commit -- main is unchanged.
#   - HEAD moves to the new branch (checkout -b) and back (switch) without any
#     commit node changing.
#   - divergence only happens after the first commit on the new branch.
#   - deleting a branch removes only the label; the commit stays if still reachable.
# ---------------------------------------------------------------------------


class TestEP03BranchingFull:
    def test_new_branch_shares_commit_with_main(self, repo: RepoTools) -> None:
        """checkout -b feature: feature + main both label the tip; HEAD -> feature.

        No new commit node appears -- branching does not copy anything.
        """
        repo.write("a.txt")
        c1 = repo.commit("first")
        repo.write("b.txt")
        c2 = repo.commit("second")
        repo.checkout("feature", new=True)
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/feature", c1, c2}
        expected_edges = {
            ("HEAD", "refs/heads/feature", "HEAD"),
            ("refs/heads/feature", c2, "branch"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "checkout -b feature")

    def test_switch_back_to_main_moves_only_head(self, repo: RepoTools) -> None:
        """switch main: HEAD re-points to main; both labels still on the tip."""
        repo.write("a.txt")
        c1 = repo.commit("first")
        repo.write("b.txt")
        c2 = repo.commit("second")
        repo.checkout("feature", new=True)
        repo.checkout("main")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/feature", c1, c2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/feature", c2, "branch"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "switch back to main")

    def test_divergence_after_commit_on_feature(self, repo: RepoTools) -> None:
        """First commit on feature: feature advances; main stays on the shared base."""
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        cf = repo.commit("feature work")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/feature", base, cf}
        expected_edges = {
            ("HEAD", "refs/heads/feature", "HEAD"),
            ("refs/heads/feature", cf, "branch"),
            (cf, base, "parent"),
            ("refs/heads/main", base, "branch"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "feature diverges")

    def test_both_branches_diverge_from_shared_base(self, repo: RepoTools) -> None:
        """Each branch commits once: two tips fork from the same parent commit."""
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        cf = repo.commit("feature work")
        repo.checkout("main")
        repo.write("main.txt")
        cm = repo.commit("main work")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/feature", base, cf, cm}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", cm, "branch"),
            (cm, base, "parent"),
            ("refs/heads/feature", cf, "branch"),
            (cf, base, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "both diverge")

    def test_deleted_branch_label_disappears(self, repo: RepoTools) -> None:
        """git branch -d temp: only the label is gone; the commit stays (reachable via main)."""
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("temp", new=True)
        repo.checkout("main")
        repo._run(["git", "branch", "-d", "temp"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", base}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", base, "branch"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "branch deleted")


# ---------------------------------------------------------------------------
# EP 04 -- The Merge Diamond
#
# Modes: normal (commit chain) + branch (topology).  Lesson beats:
#   - fast-forward: main's label advances to the feature tip; no merge commit.
#   - no-fast-forward: a merge commit appears with TWO parent edges (the diamond).
#   - branch mode: a fork node connects the two branch labels.
#
# NOTE: git writes ORIG_HEAD on every merge (the pre-merge HEAD), and visigit
# surfaces it as a safety-net ref (fix #24).  Its edge carries NO label -- it is
# a pseudo-ref, not a remote-tracking branch.
# ---------------------------------------------------------------------------


class TestEP04MergeFull:
    def test_fast_forward_merge_normal(self, repo: RepoTools) -> None:
        """FF merge: main advances to the feature tip; no merge commit node.

        Both refs end on cf; ORIG_HEAD records the pre-merge tip (base).
        """
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        cf = repo.commit("feat")
        repo.checkout("main")
        repo._run(["git", "merge", "feature"])  # fast-forward
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/feature", "ORIG_HEAD", base, cf}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", cf, "branch"),
            ("refs/heads/feature", cf, "branch"),
            (cf, base, "parent"),
            ("ORIG_HEAD", base, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "FF merge normal")

    def test_no_ff_merge_diamond_normal(self, repo: RepoTools) -> None:
        """no-FF merge: a merge commit with two parent edges -- the diamond.

        cm (merge) -> ch (hotfix) and cm -> cf (feature); both ch and cf -> base.
        ORIG_HEAD records the pre-merge tip (ch).
        """
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        cf = repo.commit("feat")
        repo.checkout("main")
        repo.write("fix.txt")
        ch = repo.commit("hotfix")
        repo.merge("feature", no_ff=True)
        cm = repo.rev_parse("HEAD")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "ORIG_HEAD",
            base,
            cf,
            ch,
            cm,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", cm, "branch"),
            (cm, ch, "parent"),
            (cm, cf, "parent"),
            (ch, base, "parent"),
            (cf, base, "parent"),
            ("refs/heads/feature", cf, "branch"),
            ("ORIG_HEAD", ch, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "no-FF diamond normal")

    def test_diverged_branch_mode_fork_at_base(self, repo: RepoTools) -> None:
        """Branch mode, diverged: fork node is the common base; fork -> each branch."""
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        repo.commit("feat")
        repo.checkout("main")
        repo.write("fix.txt")
        repo.commit("hotfix")
        nodes, edges, _ = full_graph(str(repo.path), mode="branch")
        expected_nodes = {"main", "feature", base}
        expected_edges = {(base, "main", ""), (base, "feature", "")}
        assert_exact(nodes, edges, expected_nodes, expected_edges, "branch diverged")

    def test_no_ff_merge_branch_mode_fork_at_feature_tip(self, repo: RepoTools) -> None:
        """Branch mode after no-FF merge: fork is the merge-base (the feature tip cf),
        which is now an ancestor of main; fork -> main and fork -> feature."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        cf = repo.commit("feat")
        repo.checkout("main")
        repo.write("fix.txt")
        repo.commit("hotfix")
        repo.merge("feature", no_ff=True)
        nodes, edges, _ = full_graph(str(repo.path), mode="branch")
        expected_nodes = {"main", "feature", cf}
        expected_edges = {(cf, "main", ""), (cf, "feature", "")}
        assert_exact(nodes, edges, expected_nodes, expected_edges, "branch no-FF merge")

    def test_fast_forward_branch_mode_no_fork(self, repo: RepoTools) -> None:
        """Branch mode after FF merge: no fork (both tips are the same commit);
        a direct main -> feature edge connects them."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        repo.commit("feat")
        repo.checkout("main")
        repo._run(["git", "merge", "feature"])
        nodes, edges, _ = full_graph(str(repo.path), mode="branch")
        expected_nodes = {"main", "feature"}
        expected_edges = {("main", "feature", "")}
        assert_exact(nodes, edges, expected_nodes, expected_edges, "branch FF merge")


# ---------------------------------------------------------------------------
# EP 05 -- Reset Demystified
#
# Mode: normal.  Lesson beats: all three reset modes move the branch pointer back
# by the same amount and leave the SAME graph -- the difference (index vs working
# tree) is invisible in normal mode.  ORIG_HEAD preserves the pre-reset tip.
# ---------------------------------------------------------------------------


class TestEP05ResetFull:
    @pytest.mark.parametrize("reset_mode", ["--soft", "--mixed", "--hard"])
    def test_reset_modes_produce_identical_graph(self, repo: RepoTools, reset_mode: str) -> None:
        """reset --soft / --mixed / --hard HEAD~1 all produce the same normal-mode graph.

        main moves back to c2; ORIG_HEAD keeps c3 (the pre-reset tip) reachable.
        """
        repo.write("a.txt")
        c1 = repo.commit("a")
        repo.write("b.txt")
        c2 = repo.commit("b")
        repo.write("c.txt")
        c3 = repo.commit("c")
        repo._run(["git", "reset", reset_mode, "HEAD~1"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "ORIG_HEAD", c1, c2, c3}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c2, "branch"),
            ("ORIG_HEAD", c3, ""),
            (c3, c2, "parent"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, f"reset {reset_mode}")


# ---------------------------------------------------------------------------
# EP 06 -- Detached HEAD
#
# Mode: normal.  Lesson beats: detached HEAD points directly at a commit (no
# branch ref in between); a commit made while detached is an orphan that vanishes
# once HEAD reattaches; checkout -b re-anchors the work under a branch label.
# ---------------------------------------------------------------------------


class TestEP06DetachedHeadFull:
    def test_detached_head_points_directly_at_commit(self, repo: RepoTools) -> None:
        """Detached HEAD: HEAD -> commit directly; main stays on its own tip."""
        repo.write("a.txt")
        c1 = repo.commit("a")
        repo.write("b.txt")
        c2 = repo.commit("b")
        repo.detach(c1)
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", c1, c2}
        expected_edges = {
            ("HEAD", c1, "HEAD"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "detached HEAD")

    def test_commit_in_detached_head_is_visible_orphan(self, repo: RepoTools) -> None:
        """A commit made while detached is reachable from HEAD and shows in the graph."""
        repo.write("a.txt")
        c1 = repo.commit("a")
        repo.write("b.txt")
        c2 = repo.commit("b")
        repo.detach(c1)
        repo.write("o.txt")
        orphan = repo.commit("orphan")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", c1, c2, orphan}
        expected_edges = {
            ("HEAD", orphan, "HEAD"),
            (orphan, c1, "parent"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "detached commit")

    def test_orphan_vanishes_after_reattach(self, repo: RepoTools) -> None:
        """After reattaching to main, the detached-state orphan is unreachable and gone."""
        repo.write("a.txt")
        c1 = repo.commit("a")
        repo.write("b.txt")
        c2 = repo.commit("b")
        repo.detach(c1)
        repo.write("o.txt")
        repo.commit("orphan")
        repo.checkout("main")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", c1, c2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "after reattach")

    def test_checkout_b_recovery_reanchors_work(self, repo: RepoTools) -> None:
        """checkout -b recovery from detached HEAD: HEAD attaches to the new branch."""
        repo.write("a.txt")
        c1 = repo.commit("a")
        repo.write("b.txt")
        c2 = repo.commit("b")
        repo.detach(c1)
        repo.checkout("recovery", new=True)
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/recovery", c1, c2}
        expected_edges = {
            ("HEAD", "refs/heads/recovery", "HEAD"),
            ("refs/heads/recovery", c1, "branch"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "recovery branch")


# ---------------------------------------------------------------------------
# EP 07 -- Merge vs Rebase
#
# Mode: normal.  Lesson beats: merge makes a diamond (merge commit, two parents);
# rebase replays feature onto main's tip as a NEW commit (new SHA), producing a
# linear chain.  ORIG_HEAD preserves the pre-rebase feature tip (git's safety net).
# ---------------------------------------------------------------------------


class TestEP07MergeVsRebaseFull:
    def _diverged(self, repo: RepoTools) -> tuple[str, str, str]:
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        cf = repo.commit("feat")
        repo.checkout("main")
        repo.write("fix.txt")
        ch = repo.commit("hotfix")
        return base, cf, ch

    def test_merge_path_diamond(self, repo: RepoTools) -> None:
        """Path A -- merge --no-ff: the merge commit with two parents (the diamond)."""
        base, cf, ch = self._diverged(repo)
        repo.merge("feature", no_ff=True)
        cm = repo.rev_parse("HEAD")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "ORIG_HEAD",
            base,
            cf,
            ch,
            cm,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", cm, "branch"),
            (cm, ch, "parent"),
            (cm, cf, "parent"),
            (ch, base, "parent"),
            (cf, base, "parent"),
            ("refs/heads/feature", cf, "branch"),
            ("ORIG_HEAD", ch, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "EP07 merge path")

    def test_rebase_path_linear_new_sha(self, repo: RepoTools) -> None:
        """Path B -- rebase: feature is replayed onto ch as a new commit cf_new.

        Linear chain feature -> cf_new -> ch -> base, main -> ch.  The old feature
        tip cf_old stays reachable via ORIG_HEAD (git keeps it -- it is NOT deleted).
        """
        base, cf_old, ch = self._diverged(repo)
        repo.checkout("feature")
        repo._run(["git", "rebase", "main"])
        cf_new = repo.rev_parse("HEAD")
        assert cf_new != cf_old
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/feature",
            "refs/heads/main",
            "ORIG_HEAD",
            base,
            ch,
            cf_old,
            cf_new,
        }
        expected_edges = {
            ("HEAD", "refs/heads/feature", "HEAD"),
            ("refs/heads/feature", cf_new, "branch"),
            (cf_new, ch, "parent"),
            ("refs/heads/main", ch, "branch"),
            (ch, base, "parent"),
            ("ORIG_HEAD", cf_old, ""),
            (cf_old, base, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "EP07 rebase path")


# ---------------------------------------------------------------------------
# EP 08 -- origin/main Is Not main: Remote Tracking Branches
#
# Mode: normal.  Lesson beats: pushing creates refs/remotes/origin/main; a local
# commit makes local main and origin/main diverge; fetch advances origin/main (and
# writes FETCH_HEAD) while local main trails; --exclude-remotes hides remote refs.
# ---------------------------------------------------------------------------


def _bare_remote(repo: RepoTools) -> str:
    remote_path = repo.path.parent / (repo.path.name + "_remote.git")
    import subprocess as sp

    sp.check_call(
        ["git", "init", "--bare", "-b", "main", str(remote_path)],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )
    repo._run(["git", "remote", "add", "origin", str(remote_path)])
    repo._run(["git", "push", "-u", "origin", "main"])
    return str(remote_path)


class TestEP08RemoteTrackingFull:
    def test_after_push_remote_ref_appears(self, repo: RepoTools) -> None:
        """After push: local main and origin/main both point at the single commit."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        _bare_remote(repo)
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/remotes/origin/main", c1}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c1, "branch"),
            ("refs/remotes/origin/main", c1, "remote"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "after push")

    def test_local_commit_diverges_from_origin(self, repo: RepoTools) -> None:
        """A local commit past the last push: main advances; origin/main stays behind."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        _bare_remote(repo)
        repo.write("b.txt")
        c2 = repo.commit("c2")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/remotes/origin/main", c1, c2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
            ("refs/remotes/origin/main", c1, "remote"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "local diverge")

    def test_exclude_remotes_hides_origin(self, repo: RepoTools) -> None:
        """--exclude-remotes drops refs/remotes/* but keeps local refs and commits."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        _bare_remote(repo)
        repo.write("b.txt")
        c2 = repo.commit("c2")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal", exclude_remotes=True)
        expected_nodes = {"HEAD", "refs/heads/main", c1, c2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "exclude remotes")

    def test_after_fetch_origin_ahead(self, repo: RepoTools) -> None:
        """After fetch: origin/main advances to the remote tip (and FETCH_HEAD points
        there too); local main trails.  FETCH_HEAD's edge carries no label."""
        import subprocess as sp

        repo.write("a.txt")
        c1 = repo.commit("c1")
        remote_path = _bare_remote(repo)
        clone = repo.path.parent / (repo.path.name + "_clone")
        sp.check_call(
            ["git", "clone", "--branch", "main", remote_path, str(clone)],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        for cfg in (["user.email", "t@t"], ["user.name", "T"]):
            sp.check_call(["git", "config", *cfg], cwd=clone, stderr=sp.DEVNULL)
        (clone / "x.txt").write_text("x")
        sp.check_call(["git", "add", "-A"], cwd=clone, stderr=sp.DEVNULL)
        sp.check_call(["git", "commit", "-m", "remote2"], cwd=clone, stderr=sp.DEVNULL)
        sp.check_call(
            ["git", "push", "origin", "main"], cwd=clone, stdout=sp.DEVNULL, stderr=sp.DEVNULL
        )
        cr = sp.check_output(["git", "rev-parse", "HEAD"], cwd=clone).decode().strip()
        repo._run(["git", "fetch", "origin"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/remotes/origin/main",
            "FETCH_HEAD",
            c1,
            cr,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c1, "branch"),
            ("refs/remotes/origin/main", cr, "remote"),
            ("FETCH_HEAD", cr, ""),
            (cr, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "after fetch")

    def test_origin_head_symbolic_ref_is_excluded(self, repo: RepoTools) -> None:
        """The symbolic <remote>/HEAD pointer must NOT appear -- it only mirrors the
        remote's default branch and would duplicate origin/main.  Some git versions
        create refs/remotes/origin/HEAD automatically on clone/fetch (this regression
        was caught by the oracle differential on CI)."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        _bare_remote(repo)
        repo._run(["git", "remote", "set-head", "origin", "main"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/remotes/origin/main", c1}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c1, "branch"),
            ("refs/remotes/origin/main", c1, "remote"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "origin/HEAD excluded")


# ---------------------------------------------------------------------------
# EP 09 -- Stash Is a Secret Commit
#
# Mode: verbose (stash refs only collected with include_trees).  Lesson beats:
# git stash creates a real commit -- actually a merge commit whose parents are
# the original HEAD and an index commit -- reachable via refs/stash and pointing
# at the trees/blobs of the stashed content.  Ground truth comes from git plumbing.
# ---------------------------------------------------------------------------


class TestEP09StashFull:
    def test_stash_full_object_graph(self, repo: RepoTools) -> None:
        """A stash entry is a merge commit (parents: base + index commit) with its
        own tree/blob; visigit draws the complete object graph in verbose mode."""
        repo.write("a.txt", "original")
        base = repo.commit("base")
        repo.write("a.txt", "modified")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "stash"])

        # Ground truth straight from git plumbing.
        w = repo.rev_parse("stash@{0}")  # the stash (working-tree) commit
        index_commit = repo.rev_parse("stash@{0}^2")  # the index parent commit
        base_tree = repo.rev_parse(f"{base}^{{tree}}")
        base_blob = repo.rev_parse(f"{base}:a.txt")
        stash_tree = repo.rev_parse("stash@{0}^{tree}")
        stash_blob = repo.rev_parse("stash@{0}:a.txt")

        nodes, edges, graph = full_graph(str(repo.path), mode="verbose")
        stash_ref = next(r for r in graph.refs if "stash" in r.path)

        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "ORIG_HEAD",  # git stash resets, writing ORIG_HEAD at the base
            stash_ref.path,
            base,
            w,
            index_commit,
            base_tree,
            stash_tree,
            base_blob,
            stash_blob,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", base, "branch"),
            ("ORIG_HEAD", base, ""),
            (stash_ref.path, w, ""),
            (base, base_tree, "tree"),
            (base_tree, base_blob, "a.txt"),
            (index_commit, base, "parent"),
            (index_commit, stash_tree, "tree"),
            (w, base, "parent"),
            (w, index_commit, "parent"),
            (w, stash_tree, "tree"),
            (stash_tree, stash_blob, "a.txt"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "stash verbose")

    def test_stash_absent_in_normal_mode(self, repo: RepoTools) -> None:
        """In normal mode stash refs are not collected; only the base commit shows.

        (ORIG_HEAD written by the stash also points at base, so it coincides with main.)
        """
        repo.write("a.txt", "original")
        base = repo.commit("base")
        repo.write("a.txt", "modified")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "stash"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "ORIG_HEAD", base}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", base, "branch"),
            ("ORIG_HEAD", base, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "stash normal mode")


# ---------------------------------------------------------------------------
# EP 17 -- Inside a Commit: blob, tree, commit
#
# Mode: verbose.  Lesson beats: a commit points at a root tree; a tree points at
# blobs (files) and child trees (subdirectories); each directory level is its own
# tree object.  Ground truth comes from git plumbing (rev-parse).
# ---------------------------------------------------------------------------


class TestEP17ObjectModelFull:
    def test_single_file_commit_object_graph(self, repo: RepoTools) -> None:
        """commit -> root tree -> one blob, plus HEAD -> main -> commit."""
        repo.write("hello.txt", "hello world")
        c = repo.commit("initial")
        tree = repo.rev_parse(f"{c}^{{tree}}")
        blob = repo.rev_parse(f"{c}:hello.txt")
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        expected_nodes = {"HEAD", "refs/heads/main", c, tree, blob}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c, "branch"),
            (c, tree, "tree"),
            (tree, blob, "hello.txt"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "single file")

    def test_subdirectory_object_graph(self, repo: RepoTools) -> None:
        """A subdirectory is its own child tree; the edge to it is labelled 'src'."""
        repo.write("README.md", "# r")
        repo.write("src/core.py", "x")
        c = repo.commit("with subdir")
        root = repo.rev_parse(f"{c}^{{tree}}")
        src_tree = repo.rev_parse(f"{c}:src")
        readme = repo.rev_parse(f"{c}:README.md")
        core = repo.rev_parse(f"{c}:src/core.py")
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        expected_nodes = {"HEAD", "refs/heads/main", c, root, src_tree, readme, core}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c, "branch"),
            (c, root, "tree"),
            (root, readme, "README.md"),
            (root, src_tree, "src"),
            (src_tree, core, "core.py"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "subdirectory")

    def test_nested_subdirectories_object_graph(self, repo: RepoTools) -> None:
        """Two directory levels: each is its own tree; both edges carry dir names."""
        repo.write("src/util/helper.py", "y")
        c = repo.commit("nested")
        root = repo.rev_parse(f"{c}^{{tree}}")
        src_tree = repo.rev_parse(f"{c}:src")
        util_tree = repo.rev_parse(f"{c}:src/util")
        helper = repo.rev_parse(f"{c}:src/util/helper.py")
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        expected_nodes = {"HEAD", "refs/heads/main", c, root, src_tree, util_tree, helper}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c, "branch"),
            (c, root, "tree"),
            (root, src_tree, "src"),
            (src_tree, util_tree, "util"),
            (util_tree, helper, "helper.py"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "nested subdirs")


# ---------------------------------------------------------------------------
# EP 10 -- Cherry-Pick
#
# Mode: normal.  Lesson beats: cherry-pick copies a commit's changes onto another
# branch as a NEW commit with a different SHA (different parent); the original
# commit stays on its branch.
# ---------------------------------------------------------------------------


class TestEP10CherryPickFull:
    def test_cherry_pick_creates_new_commit(self, repo: RepoTools) -> None:
        """The picked commit has a new SHA whose parent is main's tip; gem stays on feature."""
        repo.write("base.txt")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("gem.txt", "gem")
        gem = repo.commit("gem")
        repo.checkout("main")
        repo.write("mw.txt")
        mw = repo.commit("main work")
        repo._run(["git", "cherry-pick", gem])
        pick = repo.rev_parse("HEAD")
        assert pick != gem
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/feature", base, gem, mw, pick}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", pick, "branch"),
            (pick, mw, "parent"),
            (mw, base, "parent"),
            ("refs/heads/feature", gem, "branch"),
            (gem, base, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "cherry-pick")


# ---------------------------------------------------------------------------
# EP 11 -- You Didn't Lose It: git reflog
#
# Mode: normal.  Lesson beats: after reset --hard the commits are "lost" from the
# branch, but ORIG_HEAD (git's safety net) keeps the pre-reset tip reachable, and
# a new branch at that SHA makes the work permanent.
# ---------------------------------------------------------------------------


class TestEP11ReflogFull:
    def test_reset_hard_two_back_orig_head_preserves_chain(self, repo: RepoTools) -> None:
        """reset --hard HEAD~2: main moves to c1; ORIG_HEAD keeps c3 (and c2) visible."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        repo.write("b.txt")
        c2 = repo.commit("c2")
        repo.write("c.txt")
        c3 = repo.commit("c3")
        repo._run(["git", "reset", "--hard", "HEAD~2"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "ORIG_HEAD", c1, c2, c3}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c1, "branch"),
            ("ORIG_HEAD", c3, ""),
            (c3, c2, "parent"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "reset --hard ~2")

    def test_branch_recover_makes_lost_work_permanent(self, repo: RepoTools) -> None:
        """git branch recover <lost-sha>: a real ref now points at the recovered tip."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        repo.write("b.txt")
        c2 = repo.commit("c2")
        repo.write("c.txt")
        c3 = repo.commit("c3")
        repo._run(["git", "reset", "--hard", "HEAD~2"])
        repo._run(["git", "branch", "recover", c3])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/heads/recover", "ORIG_HEAD", c1, c2, c3}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c1, "branch"),
            ("refs/heads/recover", c3, "branch"),
            ("ORIG_HEAD", c3, ""),
            (c3, c2, "parent"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "branch recover")


# ---------------------------------------------------------------------------
# EP 12 -- Rewrite History: Interactive Rebase, Squash, Fixup
#
# Mode: normal.  Squash and drop are simulated with reset (+commit), which gives
# the SAME graph topology as `git rebase -i`: a new/!moved tip, the discarded
# commits unreachable from the branch but preserved via ORIG_HEAD.
# ---------------------------------------------------------------------------


class TestEP12InteractiveRebaseFull:
    def test_squash_collapses_two_into_one(self, repo: RepoTools) -> None:
        """Squash A+B into one commit on base; ORIG_HEAD keeps the old A->B chain."""
        repo.write("base.txt")
        base = repo.commit("base")
        repo.write("a.txt")
        a = repo.commit("A")
        repo.write("b.txt")
        b = repo.commit("B")
        repo._run(["git", "reset", "--soft", base])
        squash = repo.commit("squashed A+B")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "ORIG_HEAD", base, a, b, squash}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", squash, "branch"),
            (squash, base, "parent"),
            ("ORIG_HEAD", b, ""),
            (b, a, "parent"),
            (a, base, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "squash")

    def test_drop_removes_commit_from_branch(self, repo: RepoTools) -> None:
        """Drop B: main returns to A; ORIG_HEAD keeps the dropped commit visible."""
        repo.write("a.txt")
        a = repo.commit("A")
        repo.write("b.txt")
        b = repo.commit("B to drop")
        repo._run(["git", "reset", "--hard", a])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "ORIG_HEAD", a, b}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", a, "branch"),
            ("ORIG_HEAD", b, ""),
            (b, a, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "drop")


# ---------------------------------------------------------------------------
# EP 13 -- Tags Are Just Pointers (Until They Aren't)
#
# Mode: normal.  Lightweight tag: ref -> commit (one hop).  Annotated tag:
# ref -> tag object -> commit (two hops); the tag object has its own SHA.
# ---------------------------------------------------------------------------


class TestEP13TagsFull:
    def test_lightweight_and_annotated_tags(self, repo: RepoTools) -> None:
        """Both tag shapes at once: v1.0 one hop, v2.0 via an intermediate tag object."""
        repo.write("a.txt")
        c = repo.commit("release prep")
        repo.tag("v1.0", annotated=False)
        repo.tag("v2.0", annotated=True, message="rel")
        tag_obj = repo.rev_parse("refs/tags/v2.0")  # annotated -> tag object SHA
        commit_via_tag = repo.rev_parse("v2.0^{commit}")
        assert tag_obj != c and commit_via_tag == c
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "refs/tags/v1.0", "refs/tags/v2.0", tag_obj, c}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c, "branch"),
            ("refs/tags/v1.0", c, "tag"),
            ("refs/tags/v2.0", tag_obj, "tag"),
            (tag_obj, c, "commit"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "tags")


# ---------------------------------------------------------------------------
# EP 14 -- Binary Search Your Bug: git bisect
#
# Mode: normal.  During an active bisect session git writes BISECT_HEAD at the
# commit currently under test; visigit surfaces it as a ref node (with no edge
# label, like other pseudo-refs).
# ---------------------------------------------------------------------------


class TestEP14BisectFull:
    def test_bisect_head_at_midpoint(self, repo: RepoTools) -> None:
        """--no-checkout: HEAD stays on main; BISECT_HEAD marks the midpoint commit."""
        repo.write("a.txt")
        c1 = repo.commit("c1")
        repo.write("b.txt")
        c2 = repo.commit("c2")
        repo.write("c.txt")
        c3 = repo.commit("c3")
        repo._run(["git", "bisect", "start", "--no-checkout"])
        repo._run(["git", "bisect", "bad", c3])
        repo._run(["git", "bisect", "good", c1])
        midpoint = repo.rev_parse("BISECT_HEAD")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", "BISECT_HEAD", c1, c2, c3}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c3, "branch"),
            ("BISECT_HEAD", midpoint, ""),
            (c3, c2, "parent"),
            (c2, c1, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "bisect")


# ---------------------------------------------------------------------------
# EP 15 -- Two Branches, One Checkout: git worktree
#
# Mode: branch.  A branch checked out in a linked worktree is annotated with
# '[wt: <path>]' in its node LABEL; the main-worktree branch is not annotated.
# ---------------------------------------------------------------------------


class TestEP15WorktreeFull:
    def test_linked_worktree_annotation_in_label(self, repo: RepoTools) -> None:
        """feature (checked out in a linked worktree) gets [wt: path]; main does not.

        Topology: feature is ahead of main, so main -> fork(base) -> feature.
        """
        repo.write("a.txt")
        repo.commit("base")
        base = repo.rev_parse("main")
        repo.checkout("feature", new=True)
        repo.write("b.txt")
        repo.commit("feature work")
        repo.checkout("main")
        wt_path = repo.path.parent / (repo.path.name + "-wt")
        repo._run(["git", "worktree", "add", str(wt_path), "feature"])

        nodes, edges, labels, _ = build_with_labels(str(repo.path), mode="branch")
        expected_nodes = {"main", "feature", base}
        expected_edges = {(base, "feature", ""), ("main", base, "")}
        assert_exact(nodes, edges, expected_nodes, expected_edges, "worktree topology")
        # Label checks: the worktree annotation lives in the feature node's label.
        assert "[wt:" in labels["feature"], (
            f"feature label missing wt annotation: {labels['feature']!r}"
        )
        assert wt_path.as_posix() in labels["feature"]
        assert "[wt:" not in labels["main"], f"main must not be wt-annotated: {labels['main']!r}"
        assert labels["main"] == "HEAD->main"


# ---------------------------------------------------------------------------
# EP 16 -- Force Push Is Destroying Someone's History
#
# Mode: normal.  Local main and origin/main point at different commits (diverged).
# A force push moves origin/main to the local commit; the teammate's commit is
# orphaned from origin/main but stays visible via FETCH_HEAD (last fetched).
# ---------------------------------------------------------------------------


class TestEP16ForcePushFull:
    def _diverged(self, repo: RepoTools) -> tuple[str, str, str]:
        import subprocess as sp

        repo.write("base.txt")
        base = repo.commit("base")
        remote_path = repo.path.parent / (repo.path.name + "_remote.git")
        sp.check_call(
            ["git", "init", "--bare", "-b", "main", str(remote_path)],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        repo._run(["git", "remote", "add", "origin", str(remote_path)])
        repo._run(["git", "push", "-u", "origin", "main"])
        clone = repo.path.parent / (repo.path.name + "_clone")
        sp.check_call(
            ["git", "clone", "--branch", "main", str(remote_path), str(clone)],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        for cfg in (["user.email", "t@t"], ["user.name", "T"]):
            sp.check_call(["git", "config", *cfg], cwd=clone, stderr=sp.DEVNULL)
        (clone / "tm.txt").write_text("tm")
        sp.check_call(["git", "add", "-A"], cwd=clone, stderr=sp.DEVNULL)
        sp.check_call(["git", "commit", "-m", "tm"], cwd=clone, stderr=sp.DEVNULL)
        sp.check_call(
            ["git", "push", "origin", "main"], cwd=clone, stdout=sp.DEVNULL, stderr=sp.DEVNULL
        )
        tm = sp.check_output(["git", "rev-parse", "HEAD"], cwd=clone).decode().strip()
        repo._run(["git", "fetch", "origin"])
        repo.write("local.txt")
        loc = repo.commit("local-only")
        return base, tm, loc

    def test_diverged_state(self, repo: RepoTools) -> None:
        """Before force push: main -> loc, origin/main -> tm (teammate); FETCH_HEAD -> tm."""
        base, tm, loc = self._diverged(repo)
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/remotes/origin/main",
            "FETCH_HEAD",
            base,
            tm,
            loc,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", loc, "branch"),
            (loc, base, "parent"),
            ("refs/remotes/origin/main", tm, "remote"),
            ("FETCH_HEAD", tm, ""),
            (tm, base, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "diverged")

    def test_force_push_moves_origin_main(self, repo: RepoTools) -> None:
        """After force push: origin/main -> loc; tm orphaned from origin/main but
        still shown via FETCH_HEAD (the last-fetched ref, unchanged by the push)."""
        base, tm, loc = self._diverged(repo)
        repo._run(["git", "push", "--force", "origin", "main"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/remotes/origin/main",
            "FETCH_HEAD",
            base,
            tm,
            loc,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", loc, "branch"),
            (loc, base, "parent"),
            ("refs/remotes/origin/main", loc, "remote"),
            ("FETCH_HEAD", tm, ""),
            (tm, base, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "after force push")


# ---------------------------------------------------------------------------
# EP 18 -- Same File, Same SHA: content-addressable storage
#
# Mode: verbose.  An unchanged file shares one blob node across commits; a changed
# file gets a new blob.  Each commit has its own tree.
# ---------------------------------------------------------------------------


class TestEP18ContentAddressableFull:
    def test_shared_blob_across_two_commits(self, repo: RepoTools) -> None:
        """README.md (unchanged) is one shared blob node; app.py gets a new blob."""
        repo.write("README.md", "# shared")
        repo.write("app.py", "v1")
        c1 = repo.commit("c1")
        repo.write("app.py", "v2")
        c2 = repo.commit("c2")
        tree1 = repo.rev_parse(f"{c1}^{{tree}}")
        tree2 = repo.rev_parse(f"{c2}^{{tree}}")
        readme = repo.rev_parse(f"{c1}:README.md")
        assert readme == repo.rev_parse(f"{c2}:README.md")  # shared blob
        app1 = repo.rev_parse(f"{c1}:app.py")
        app2 = repo.rev_parse(f"{c2}:app.py")
        assert app1 != app2
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        expected_nodes = {"HEAD", "refs/heads/main", c1, c2, tree1, tree2, readme, app1, app2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
            (c2, tree2, "tree"),
            (c1, tree1, "tree"),
            (tree2, app2, "app.py"),
            (tree2, readme, "README.md"),
            (tree1, app1, "app.py"),
            (tree1, readme, "README.md"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "shared blob")


# ---------------------------------------------------------------------------
# EP 19 -- The Staging Area Exposed
#
# Mode: verbose.  git add writes a blob and records it in the index.  visigit
# shows Staged / Unstaged / Untracked boxes alongside the committed object graph,
# and the staged box appears even before the first commit (unborn HEAD).
# ---------------------------------------------------------------------------


class TestEP19StagingFull:
    def test_three_boxes_with_committed_graph(self, repo: RepoTools) -> None:
        """Staged, unstaged, and untracked boxes co-exist with the committed object graph."""
        repo.write("committed.txt", "committed")
        c = repo.commit("base")
        tree = repo.rev_parse(f"{c}^{{tree}}")
        blob = repo.rev_parse(f"{c}:committed.txt")
        repo.write("committed.txt", "modified")  # unstaged
        repo.write("staged.txt", "staged")
        repo._run(["git", "add", "staged.txt"])  # staged
        repo.write("untracked.txt", "u")  # untracked
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            c,
            tree,
            blob,
            "Staged Changes",
            "staged|staged.txt",
            "Unstaged Changes",
            "unstaged|committed.txt",
            "Untracked",
            "untracked|untracked.txt",
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c, "branch"),
            (c, tree, "tree"),
            (tree, blob, "committed.txt"),
            ("Staged Changes", "staged|staged.txt", "staged.txt"),
            ("Unstaged Changes", "unstaged|committed.txt", "committed.txt"),
            ("Untracked", "untracked|untracked.txt", "untracked.txt"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "three boxes")

    def test_staged_before_first_commit(self, repo: RepoTools) -> None:
        """Unborn HEAD: a staged file shows just the Staged Changes box (no commit graph,
        no empty-repo message)."""
        repo.write("README.md", "# Hello")
        repo._run(["git", "add", "README.md"])
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        expected_nodes = {"Staged Changes", "staged|README.md"}
        expected_edges = {("Staged Changes", "staged|README.md", "README.md")}
        assert_exact(nodes, edges, expected_nodes, expected_edges, "staged unborn")


# ---------------------------------------------------------------------------
# EP 20 -- All the Way Down: git cat-file, .git/objects, Pack Files
#
# Mode: verbose.  After git gc packs loose objects, GitPython reads the pack
# transparently: visigit shows exactly the same object graph, deduplication
# preserved.
# ---------------------------------------------------------------------------


class TestEP20PackFilesFull:
    def test_object_graph_unchanged_after_gc(self, repo: RepoTools) -> None:
        """The full verbose object graph is identical before and after git gc."""
        repo.write("unchanged.txt", "same")
        repo.write("changing.txt", "v1")
        c1 = repo.commit("c1")
        repo.write("changing.txt", "v2")
        c2 = repo.commit("c2")
        tree1 = repo.rev_parse(f"{c1}^{{tree}}")
        tree2 = repo.rev_parse(f"{c2}^{{tree}}")
        unchanged = repo.rev_parse(f"{c1}:unchanged.txt")
        assert unchanged == repo.rev_parse(f"{c2}:unchanged.txt")
        chg1 = repo.rev_parse(f"{c1}:changing.txt")
        chg2 = repo.rev_parse(f"{c2}:changing.txt")

        expected_nodes = {"HEAD", "refs/heads/main", c1, c2, tree1, tree2, unchanged, chg1, chg2}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c2, "branch"),
            (c2, c1, "parent"),
            (c2, tree2, "tree"),
            (c1, tree1, "tree"),
            (tree2, chg2, "changing.txt"),
            (tree2, unchanged, "unchanged.txt"),
            (tree1, chg1, "changing.txt"),
            (tree1, unchanged, "unchanged.txt"),
        }
        # Before gc
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        assert_exact(nodes, edges, expected_nodes, expected_edges, "before gc")
        # After gc -- identical
        repo._run(["git", "gc", "--quiet"])
        nodes, edges, _ = full_graph(str(repo.path), mode="verbose")
        assert_exact(nodes, edges, expected_nodes, expected_edges, "after gc")


# ---------------------------------------------------------------------------
# Conflict states and special object types
#
# In-progress merge/cherry-pick conflicts write MERGE_HEAD / CHERRY_PICK_HEAD
# (EP04 / EP10 brief mentions); a submodule is a gitlink object (EP17's "fourth
# object type" territory).  These exercise the pseudo-ref edge-label fix and the
# distinct gitlink node rendering.
# ---------------------------------------------------------------------------


class TestConflictAndSpecialObjectsFull:
    def test_merge_conflict_shows_merge_head(self, repo: RepoTools) -> None:
        """An in-progress merge conflict: MERGE_HEAD -> the merged commit (no label).

        git merge also writes ORIG_HEAD at the pre-merge tip even on conflict.
        """
        import subprocess as sp

        repo.write("f.txt", "base")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("f.txt", "feature")
        feat = repo.commit("feature change")
        repo.checkout("main")
        repo.write("f.txt", "main")
        main_chg = repo.commit("main change")
        try:
            repo._run(["git", "merge", "feature"])
        except sp.CalledProcessError:
            pass  # conflict expected
        assert (repo.path / ".git" / "MERGE_HEAD").exists()
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "MERGE_HEAD",
            "ORIG_HEAD",
            base,
            feat,
            main_chg,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", main_chg, "branch"),
            (main_chg, base, "parent"),
            ("refs/heads/feature", feat, "branch"),
            (feat, base, "parent"),
            ("MERGE_HEAD", feat, ""),
            ("ORIG_HEAD", main_chg, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "merge conflict")

    def test_cherry_pick_conflict_shows_cherry_pick_head(self, repo: RepoTools) -> None:
        """An in-progress cherry-pick conflict: CHERRY_PICK_HEAD -> the applied commit
        (no label).  Cherry-pick does NOT write ORIG_HEAD."""
        import subprocess as sp

        repo.write("f.txt", "v1")
        base = repo.commit("init")
        repo.checkout("feature", new=True)
        repo.write("f.txt", "feature")
        feat = repo.commit("feature change")
        repo.checkout("main")
        repo.write("f.txt", "main")
        main_div = repo.commit("main diverges")
        try:
            repo._run(["git", "cherry-pick", feat])
        except sp.CalledProcessError:
            pass  # conflict expected
        assert (repo.path / ".git" / "CHERRY_PICK_HEAD").exists()
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "CHERRY_PICK_HEAD",
            base,
            feat,
            main_div,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", main_div, "branch"),
            (main_div, base, "parent"),
            ("refs/heads/feature", feat, "branch"),
            (feat, base, "parent"),
            ("CHERRY_PICK_HEAD", feat, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "cherry-pick conflict")

    def test_submodule_gitlink_object_graph(self, repo: RepoTools) -> None:
        """A submodule is a gitlink node (gitlink|<sha>), distinct from a blob; its
        tree edge is labelled with the submodule directory name ('lib')."""
        import subprocess as sp

        sub = repo.path.parent / (repo.path.name + "_sub")
        sp.check_call(["git", "init", "-b", "main", str(sub)], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        for cfg in (["user.email", "s@s"], ["user.name", "S"]):
            sp.check_call(["git", "config", *cfg], cwd=sub, stderr=sp.DEVNULL)
        (sub / "sub.txt").write_text("s")
        sp.check_call(["git", "add", "-A"], cwd=sub, stderr=sp.DEVNULL)
        sp.check_call(["git", "commit", "-m", "subinit"], cwd=sub, stderr=sp.DEVNULL)
        sub_sha = sp.check_output(["git", "rev-parse", "HEAD"], cwd=sub).decode().strip()

        repo.write("main.txt")
        repo._run(["git", "add", "main.txt"])
        repo._run(
            ["git", "-c", "protocol.file.allow=always", "submodule", "add", sub.as_posix(), "lib"]
        )
        c = repo.commit("add submodule")
        tree = repo.rev_parse(f"{c}^{{tree}}")
        main_blob = repo.rev_parse(f"{c}:main.txt")
        gitmodules_blob = repo.rev_parse(f"{c}:.gitmodules")
        gitlink = f"gitlink|{sub_sha}"

        nodes, edges, labels, _ = build_with_labels(str(repo.path), mode="verbose")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            c,
            tree,
            main_blob,
            gitmodules_blob,
            gitlink,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", c, "branch"),
            (c, tree, "tree"),
            (tree, main_blob, "main.txt"),
            (tree, gitmodules_blob, ".gitmodules"),
            (tree, gitlink, "lib"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "submodule gitlink")
        # The gitlink node is labelled "gitlink", distinguishing it from a blob.
        assert labels[gitlink].startswith("gitlink"), f"gitlink label: {labels[gitlink]!r}"


# ---------------------------------------------------------------------------
# EP 05 -- Resolving Merge Conflicts (resolve / abort)
#
# Mode: normal.  A conflicting merge writes MERGE_HEAD; resolving + committing
# produces the merge commit (two parents) and clears MERGE_HEAD; --abort returns
# to the pre-merge tip.  git merge writes ORIG_HEAD either way.
# ---------------------------------------------------------------------------


class TestEP05MergeConflictResolveFull:
    def _conflict(self, repo: RepoTools) -> tuple[str, str, str]:
        import subprocess as sp

        repo.write("f.txt", "base")
        base = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("f.txt", "feature")
        feat = repo.commit("feature change")
        repo.checkout("main")
        repo.write("f.txt", "main")
        main_chg = repo.commit("main change")
        try:
            repo._run(["git", "merge", "feature"])
        except sp.CalledProcessError:
            pass  # conflict expected
        return base, feat, main_chg

    def test_resolved_conflict_becomes_merge_commit(self, repo: RepoTools) -> None:
        """After resolving + committing: a merge commit with two parents; MERGE_HEAD gone."""
        base, feat, main_chg = self._conflict(repo)
        repo.write("f.txt", "resolved")  # resolve
        repo._run(["git", "add", "f.txt"])
        repo._run(["git", "commit", "--no-edit"])
        cm = repo.rev_parse("HEAD")
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "ORIG_HEAD",
            base,
            feat,
            main_chg,
            cm,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", cm, "branch"),
            (cm, main_chg, "parent"),
            (cm, feat, "parent"),
            (main_chg, base, "parent"),
            (feat, base, "parent"),
            ("refs/heads/feature", feat, "branch"),
            ("ORIG_HEAD", main_chg, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "conflict resolved")
        assert "MERGE_HEAD" not in nodes

    def test_aborted_conflict_returns_to_pre_merge(self, repo: RepoTools) -> None:
        """git merge --abort: back to the pre-merge tip; MERGE_HEAD gone, no merge commit."""
        base, feat, main_chg = self._conflict(repo)
        repo._run(["git", "merge", "--abort"])
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {
            "HEAD",
            "refs/heads/main",
            "refs/heads/feature",
            "ORIG_HEAD",
            base,
            feat,
            main_chg,
        }
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", main_chg, "branch"),
            (main_chg, base, "parent"),
            ("refs/heads/feature", feat, "branch"),
            (feat, base, "parent"),
            ("ORIG_HEAD", main_chg, ""),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "merge aborted")
        assert "MERGE_HEAD" not in nodes


# ---------------------------------------------------------------------------
# EP 07 -- Undo Without Fear: revert vs amend
#
# Mode: normal.  revert ADDS a new inverse commit (chain grows).  amend REPLACES
# the last commit with a new SHA and -- uniquely -- writes NO ORIG_HEAD, so the
# old commit is gone from the graph.
# ---------------------------------------------------------------------------


class TestEP07UndoFull:
    def test_revert_adds_new_commit(self, repo: RepoTools) -> None:
        """git revert: a new commit on top; the original commit stays. No ORIG_HEAD."""
        repo.write("a.txt")
        a = repo.commit("a")
        repo.write("b.txt")
        b = repo.commit("b")
        repo._run(["git", "revert", "--no-edit", b])
        rev = repo.rev_parse("HEAD")
        assert rev != b
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", a, b, rev}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", rev, "branch"),
            (rev, b, "parent"),
            (b, a, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "revert")

    def test_amend_replaces_last_commit_with_no_safety_net(self, repo: RepoTools) -> None:
        """git commit --amend: a new-SHA commit replaces the old one, which VANISHES
        (amend writes no ORIG_HEAD -- the old commit is only in the reflog)."""
        repo.write("a.txt")
        a = repo.commit("a")
        repo.write("b.txt")
        old_b = repo.commit("b")
        repo.write("b.txt", "amended")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "commit", "--amend", "--no-edit"])
        amended = repo.rev_parse("HEAD")
        assert amended != old_b
        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        expected_nodes = {"HEAD", "refs/heads/main", a, amended}
        expected_edges = {
            ("HEAD", "refs/heads/main", "HEAD"),
            ("refs/heads/main", amended, "branch"),
            (amended, a, "parent"),
        }
        assert_exact(nodes, edges, expected_nodes, expected_edges, "amend")
        # The distinguishing teaching point: no safety-net ref, old commit gone.
        assert old_b not in nodes
        assert "ORIG_HEAD" not in nodes


# ---------------------------------------------------------------------------
# EP 11 -- Two Repos, One Screen: local + origin (bare)
#
# Mode: all.  A bare "origin" on the same machine renders as its own commit graph
# (no index boxes).  After push it holds the pushed commit; a local-only commit
# does not appear in origin until pushed.
# ---------------------------------------------------------------------------


class TestEP11TwoReposFull:
    def test_bare_origin_holds_pushed_commits_only(self, repo: RepoTools) -> None:
        import subprocess as sp

        repo.write("a.txt")
        c1 = repo.commit("c1")
        bare = repo.path.parent / (repo.path.name + "_origin.git")
        sp.check_call(
            ["git", "init", "--bare", "-b", "main", str(bare)],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        repo._run(["git", "remote", "add", "origin", str(bare)])
        repo._run(["git", "push", "-u", "origin", "main"])

        # The bare origin renders as its own graph and matches the oracle exactly.
        bnodes, _bedges, _ = full_graph(str(bare), mode="normal")
        assert c1 in bnodes
        assert_matches_git(str(bare), "normal")
        assert_matches_git(str(bare), "verbose")  # bare -> trivially clean

        # A local-only commit does not appear in origin until pushed.
        repo.write("b.txt")
        c2 = repo.commit("c2")
        bnodes2, _b2, _ = full_graph(str(bare), mode="normal")
        assert c1 in bnodes2
        assert c2 not in bnodes2


# ---------------------------------------------------------------------------
# EP 15 -- Git's Safety Nets: pseudo-refs carry no edge label
#
# Mode: normal.  ORIG_HEAD (reset) and FETCH_HEAD (fetch) are real ref nodes but
# carry NO edge label (they are not branch/tag/remote).
# ---------------------------------------------------------------------------


class TestEP15SafetyNetsFull:
    def test_orig_head_and_fetch_head_have_no_edge_label(self, repo: RepoTools) -> None:
        import subprocess as sp

        repo.write("a.txt")
        repo.commit("c1")
        remote = repo.path.parent / (repo.path.name + "_remote.git")
        sp.check_call(
            ["git", "init", "--bare", "-b", "main", str(remote)],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
        )
        repo._run(["git", "remote", "add", "origin", str(remote)])
        repo._run(["git", "push", "-u", "origin", "main"])
        repo.write("b.txt")
        repo.commit("c2")
        repo._run(["git", "fetch", "origin"])  # writes FETCH_HEAD
        repo._run(["git", "reset", "--hard", "HEAD"])  # writes ORIG_HEAD

        nodes, edges, _ = full_graph(str(repo.path), mode="normal")
        assert "ORIG_HEAD" in nodes and "FETCH_HEAD" in nodes
        for ref in ("ORIG_HEAD", "FETCH_HEAD"):
            ref_labels = {lbl for (frm, _to, lbl) in edges if frm == ref}
            assert ref_labels == {""}, f"{ref} edges must carry no label, got {ref_labels}"


# ---------------------------------------------------------------------------
# EP 22 -- Submodules vs Subtrees
#
# Mode: verbose.  A subtree is NOT a distinct object: `git subtree add` merges the
# upstream files in as ordinary blobs (no gitlink) and records the upstream
# history as a second parent.  (Submodule/gitlink is covered above.)
# ---------------------------------------------------------------------------


def _has_git_subtree() -> bool:
    import subprocess

    return subprocess.run(["git", "subtree", "--help"], capture_output=True).returncode == 0


_HAS_SUBTREE = _has_git_subtree()


class TestEP22SubtreeFull:
    @pytest.mark.skipif(not _HAS_SUBTREE, reason="git subtree not available")
    def test_subtree_add_merges_normal_files_no_gitlink(self, repo: RepoTools) -> None:
        import subprocess as sp

        lib = repo.path.parent / (repo.path.name + "_lib")
        sp.check_call(["git", "init", "-b", "main", str(lib)], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        for cfg in (["user.email", "l@l"], ["user.name", "L"]):
            sp.check_call(["git", "config", *cfg], cwd=lib, stderr=sp.DEVNULL)
        (lib / "lib.py").write_text("lib v1")
        sp.check_call(["git", "add", "-A"], cwd=lib, stderr=sp.DEVNULL)
        sp.check_call(["git", "commit", "-m", "lib init"], cwd=lib, stderr=sp.DEVNULL)

        repo.write("main.py", "app")
        repo.commit("app init")
        repo._run(["git", "subtree", "add", "--prefix=vendor/lib", str(lib), "main"])

        nodes, edges, _labels, _graph = build_with_labels(str(repo.path), mode="verbose")
        # A subtree is NOT a submodule: no gitlink node anywhere.
        assert not any(n.startswith("gitlink|") for n in nodes), "subtree must not create a gitlink"
        # The library file is a NORMAL blob, reachable under the prefix.
        lib_blob = repo.rev_parse("HEAD:vendor/lib/lib.py")
        assert lib_blob in nodes
        # The subtree-add commit is a MERGE (two parents).
        head = repo.rev_parse("HEAD")
        parents = repo._run(["git", "rev-list", "--parents", "-n", "1", "HEAD"]).split()[1:]
        assert len(parents) == 2, "git subtree add creates a merge commit"
        for p in parents:
            assert (head, p, "parent") in edges
        # Exhaustive correctness is enforced by the autouse oracle cross-check.
