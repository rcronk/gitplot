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

from .conftest import RepoTools

# An edge is identified by (from_id, to_id, label) -- labels matter for teaching
# accuracy (e.g. "HEAD" vs "branch" vs "parent" vs a filename).
Edge = tuple[str, str, str]


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
    git_repo = GitRepo(repo_path)
    include_trees = mode == "verbose"
    graph = git_repo.build_graph(include_trees=include_trees, exclude_remotes=exclude_remotes)
    index_state = git_repo.get_index_state() if mode == "verbose" else None
    branch_topo = git_repo.get_branch_topology() if mode == "branch" else None
    builder = GraphBuilder(mode=mode, **kwargs)
    builder.build(graph, index_state=index_state, branch_topology=branch_topo)
    nodes = set(builder.node_ids)
    edges = set(builder._rendered_edges)
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
