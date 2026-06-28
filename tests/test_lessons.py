"""Walkthrough integration tests for the Visible Git curriculum.

Each test class mirrors a lesson episode and verifies that gitplot produces
the correct DOT graph structure for the git state described in that video.

Running these tests catches gitplot bugs that would cause incorrect diagrams
during lesson recording. Tests use structural assertions (node/edge presence)
rather than golden files so they survive cosmetic layout changes.

Run with:
    pytest tests/test_lessons.py -v
"""

from __future__ import annotations

import subprocess

from gitplot.builder import GraphBuilder
from gitplot.repo import GitRepo

from .conftest import RepoTools, edge_in, node_in


def _fork_sha_labels(src: str) -> list[str]:
    """Extract the full SHA node IDs of fork commit nodes from a branch-mode DOT source.

    Fork nodes have labels like label="fork\\n<short_sha>" where \\n is an actual
    newline character in the graphviz Python output.

    Graphviz quotes SHA node IDs when they start with a digit (e.g. "0abc...") but
    leaves them unquoted when they start with a letter (e.g. f09d...).  The regex
    handles both forms with an optional leading/trailing double-quote.
    """
    import re

    # "? matches the optional leading quote; "? at the end matches optional trailing quote
    # \n in the raw regex string is the regex metacharacter matching actual newline chr(10)
    return re.findall(r'"?([0-9a-f]{40})"?\s*\[label="fork\n', src)


def _build(
    repo_path: str,
    mode: str = "normal",
    exclude_remotes: bool = False,
    **kwargs,
):
    """Build a gitplot graph from a real repo path; return (Digraph, GraphBuilder, RepoGraph)."""
    git_repo = GitRepo(repo_path)
    include_trees = mode == "verbose"
    graph = git_repo.build_graph(include_trees=include_trees, exclude_remotes=exclude_remotes)
    index_state = git_repo.get_index_state() if mode == "verbose" else None
    branch_topo = git_repo.get_branch_topology() if mode == "branch" else None
    builder = GraphBuilder(mode=mode, **kwargs)
    dg = builder.build(graph, index_state=index_state, branch_topology=branch_topo)
    return dg, builder, graph


# ---------------------------------------------------------------------------
# EP 02 — Your First Repository
# Lesson: HEAD → branch → commit chain appears on first commit; grows with each new commit.
# ---------------------------------------------------------------------------


class TestLesson02FirstRepo:
    def test_head_and_branch_after_first_commit(self, repo: RepoTools) -> None:
        """After git commit: HEAD, refs/heads/main, and the commit SHA all appear."""
        repo.write("README.md", "# Hello")
        sha = repo.commit("initial commit")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "HEAD")
        assert node_in(src, "refs/heads/main")
        assert node_in(src, sha)
        assert edge_in(src, "HEAD", "refs/heads/main")
        assert edge_in(src, "refs/heads/main", sha)

    def test_commit_chain_grows_with_second_commit(self, repo: RepoTools) -> None:
        """Second commit node appears with a parent edge pointing to the first commit."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, sha2)
        assert node_in(src, sha1)
        assert edge_in(src, sha2, sha1)
        assert edge_in(src, "refs/heads/main", sha2)

    def test_boring_chain_collapsed_into_summary_node(self, repo: RepoTools) -> None:
        """Boring middle commits collapse into a summary node in normal mode.

        With 5 commits total: commit 1 (initial, 0 parents) and commit 5 (tip, has ref) are
        not boring.  Commits 2-4 are boring (1 parent, 1 child, 0 refs) and collapse into one
        summary node labelled "sha (3) sha".
        """
        import re

        repo.write("base.txt")
        repo.commit("first")
        # Add four more unremarkable commits — commits 2-4 form a boring run
        for i in range(4):
            repo.write(f"file{i}.txt")
            sha_last = repo.commit(f"commit {i + 2}")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        # The tip and the branch ref are always visible
        assert node_in(src, "refs/heads/main")
        assert node_in(src, sha_last)
        # Boring commits 2-4 collapse into one summary node; label format is "sha (N) sha"
        # Presence of "(3)" (or any "(N)") confirms the collapse happened
        assert re.search(r"\(\d+\)", src), (
            "Boring-run summary node must have a label like 'sha (N) sha'"
        )
        # Only 2 full 'commit\n...' nodes should exist (first + tip);
        # the 3 boring commits in between produce a summary node, not 3 commit nodes
        commit_node_defs = src.count('"commit\\n')
        assert commit_node_defs <= 2, (
            f"Expected at most 2 full commit nodes (first + tip); found {commit_node_defs}. "
            "Boring-run collapse may be broken."
        )


# ---------------------------------------------------------------------------
# EP 03 — Branching Out
# Lesson: a new branch is just a pointer to an existing commit; divergence happens
#         only after the first commit on the new branch.
# ---------------------------------------------------------------------------


class TestLesson03Branching:
    def test_new_branch_shares_commit_with_main(self, repo: RepoTools) -> None:
        """git checkout -b feature: both main and feature point to the same commit SHA."""
        repo.write("base.txt")
        sha = repo.commit("base")
        repo.checkout("feature", new=True)
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/heads/main")
        assert node_in(src, "refs/heads/feature")
        assert edge_in(src, "refs/heads/main", sha)
        assert edge_in(src, "refs/heads/feature", sha)

    def test_feature_diverges_from_main_after_commit(self, repo: RepoTools) -> None:
        """Feature commit advances feature tip; main stays behind on the shared base."""
        repo.write("base.txt")
        base_sha = repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        feature_sha = repo.commit("add feature")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/feature", feature_sha)
        assert edge_in(src, "refs/heads/main", base_sha)
        assert edge_in(src, feature_sha, base_sha)

    def test_deleted_branch_label_disappears(self, repo: RepoTools) -> None:
        """After git branch -d: the branch ref node is gone; the commit remains."""
        repo.write("base.txt")
        sha = repo.commit("base")
        repo.checkout("temp", new=True)
        repo.checkout("main")
        repo._run(["git", "branch", "-d", "temp"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert not node_in(src, "refs/heads/temp")
        assert node_in(src, sha)


# ---------------------------------------------------------------------------
# EP 04 — The Merge Diamond
# Lesson: fast-forward simply moves a pointer; --no-ff creates a merge commit
#         with two parent edges, forming a diamond.
# ---------------------------------------------------------------------------


class TestLesson04Merging:
    def test_fast_forward_merge_moves_main_to_feature_tip(self, repo: RepoTools) -> None:
        """Fast-forward: main label jumps to feature tip; no extra merge commit node."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        sha_feature = repo.commit("add feature")
        repo.checkout("main")
        repo._run(["git", "merge", "feature"])  # fast-forward by default
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        # main now points directly to what was the feature tip
        assert edge_in(src, "refs/heads/main", sha_feature)

    def test_no_ff_merge_creates_merge_commit_with_two_parents(self, repo: RepoTools) -> None:
        """--no-ff: merge commit appears with edges to both parents (the diamond)."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        feature_sha = repo.commit("add feature")
        repo.checkout("main")
        repo.write("fix.txt")
        hotfix_sha = repo.commit("hotfix")
        repo.merge("feature", no_ff=True)
        merge_sha = repo.rev_parse("HEAD")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, merge_sha)
        assert edge_in(src, merge_sha, hotfix_sha)
        assert edge_in(src, merge_sha, feature_sha)

    def test_conflicting_merge_shows_merge_head_in_graph(self, repo: RepoTools) -> None:
        """Fix #24: an in-progress merge conflict writes MERGE_HEAD into the graph.

        When 'git merge' stops with a conflict, git writes .git/MERGE_HEAD pointing
        at the commit being merged in.  gitplot now surfaces this as a visible ref node.
        """
        import subprocess

        repo.write("file.txt", "base")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("file.txt", "feature version")
        feature_sha = repo.commit("feature change")
        repo.checkout("main")
        repo.write("file.txt", "main version")
        repo.commit("main change")
        try:
            repo._run(["git", "merge", "feature"])
        except subprocess.CalledProcessError:
            pass  # conflict expected
        assert (repo.path / ".git" / "MERGE_HEAD").exists()

        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "MERGE_HEAD"), "MERGE_HEAD node must appear during merge conflict"
        assert edge_in(src, "MERGE_HEAD", feature_sha), "MERGE_HEAD must point at the merged commit"
        # DOT label accuracy: the node label should be the bare string "MERGE_HEAD"
        assert "MERGE_HEAD" in src

    def test_no_ff_merge_in_branch_mode_shows_fork(self, repo: RepoTools) -> None:
        """Branch mode: diverged branches connect through a fork node."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        repo.commit("add feature")
        repo.checkout("main")
        repo.write("fix.txt")
        repo.commit("hotfix")
        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source
        assert node_in(src, "main")
        assert node_in(src, "feature")
        assert "fork" in src


# ---------------------------------------------------------------------------
# EP 05 — Reset Demystified
# Lesson: all three modes move the branch pointer back; the commit node disappears
#         from the graph because it becomes unreachable from any ref.
# ---------------------------------------------------------------------------


class TestLesson05Reset:
    def _two_commits(self, repo: RepoTools) -> tuple[str, str]:
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second")
        return sha1, sha2

    def test_reset_soft_moves_branch_pointer_back(self, repo: RepoTools) -> None:
        """After reset --soft HEAD~1: main points to the first commit.

        git reset --soft writes ORIG_HEAD pointing at sha2 (the pre-reset tip), so sha2
        stays visible in the graph via ORIG_HEAD even though main no longer points to it.
        """
        sha1, sha2 = self._two_commits(repo)
        repo._run(["git", "reset", "--soft", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/main", sha1)
        assert not edge_in(src, "refs/heads/main", sha2)
        # All git reset modes write ORIG_HEAD -- feat #24 makes it visible in the graph
        assert node_in(src, "ORIG_HEAD"), "ORIG_HEAD must appear after git reset --soft"
        assert edge_in(src, "ORIG_HEAD", sha2), "ORIG_HEAD must point at the pre-reset commit"

    def test_reset_mixed_moves_branch_pointer_back(self, repo: RepoTools) -> None:
        """After reset --mixed HEAD~1: same pointer movement as --soft.

        git reset --mixed also writes ORIG_HEAD, keeping sha2 reachable.
        """
        sha1, sha2 = self._two_commits(repo)
        repo._run(["git", "reset", "--mixed", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/main", sha1)
        assert not edge_in(src, "refs/heads/main", sha2)
        assert node_in(src, "ORIG_HEAD"), "ORIG_HEAD must appear after git reset --mixed"
        assert edge_in(src, "ORIG_HEAD", sha2), "ORIG_HEAD must point at the pre-reset commit"

    def test_reset_hard_moves_branch_pointer_back(self, repo: RepoTools) -> None:
        """After reset --hard HEAD~1: same pointer movement; working tree also wiped.

        git reset --hard writes ORIG_HEAD, keeping sha2 visible as a safety net.
        """
        sha1, sha2 = self._two_commits(repo)
        repo._run(["git", "reset", "--hard", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/main", sha1)
        assert not edge_in(src, "refs/heads/main", sha2)
        assert node_in(src, "ORIG_HEAD"), "ORIG_HEAD must appear after git reset --hard"
        assert edge_in(src, "ORIG_HEAD", sha2), "ORIG_HEAD must point at the pre-reset commit"


# ---------------------------------------------------------------------------
# EP 06 — Detached HEAD
# Lesson: detached HEAD means HEAD points directly to a commit SHA rather than
#         through a branch ref. Creating a branch from that state re-anchors the work.
# ---------------------------------------------------------------------------


class TestLesson06DetachedHead:
    def test_detached_head_points_directly_to_commit(self, repo: RepoTools) -> None:
        """Detached HEAD: HEAD → commit (no branch ref in between)."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        repo.commit("second")
        repo.detach(sha1)
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "HEAD")
        assert edge_in(src, "HEAD", sha1)
        assert not edge_in(src, "HEAD", "refs/heads/main")

    def test_creating_branch_from_detached_head_reattaches(self, repo: RepoTools) -> None:
        """git checkout -b recovery from detached HEAD: new branch appears and HEAD attaches."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        repo.commit("second")
        repo.detach(sha1)
        repo.checkout("recovery", new=True)
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/heads/recovery")
        assert edge_in(src, "HEAD", "refs/heads/recovery")


# ---------------------------------------------------------------------------
# EP 07 — Merge vs Rebase
# Lesson: merge creates a diamond with a merge commit; rebase replays commits
#         onto the target, producing a linear history with new SHAs.
# ---------------------------------------------------------------------------


class TestLesson07RebaseVsMerge:
    def _diverged_repo(self, repo: RepoTools) -> tuple[str, str]:
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        feature_sha = repo.commit("add feature")
        repo.checkout("main")
        repo.write("fix.txt")
        hotfix_sha = repo.commit("hotfix on main")
        return feature_sha, hotfix_sha

    def test_merge_no_ff_produces_two_parent_edges(self, repo: RepoTools) -> None:
        """Merge: merge commit has edges to both integration points (diamond shape)."""
        feature_sha, hotfix_sha = self._diverged_repo(repo)
        repo.merge("feature", no_ff=True)
        merge_sha = repo.rev_parse("HEAD")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, merge_sha, hotfix_sha)
        assert edge_in(src, merge_sha, feature_sha)

    def test_rebase_creates_linear_history_with_new_sha(self, repo: RepoTools) -> None:
        """Rebase: feature commit replayed with a new SHA; parent is main's tip; no merge commit."""
        feature_sha, hotfix_sha = self._diverged_repo(repo)
        repo.checkout("feature")
        repo._run(["git", "rebase", "main"])
        new_feature_sha = repo.rev_parse("HEAD")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert new_feature_sha != feature_sha, "Rebased commit must have a new SHA"
        assert node_in(src, new_feature_sha)
        assert edge_in(src, new_feature_sha, hotfix_sha)
        assert not edge_in(src, new_feature_sha, feature_sha)


# ---------------------------------------------------------------------------
# EP 09 — Stash
# Lesson: stash creates a real commit accessible via refs/stash, visible only
#         in verbose mode (include_stash is enabled with include_trees).
# ---------------------------------------------------------------------------


class TestLesson09Stash:
    def test_stash_appears_as_ref_in_verbose_mode(self, repo: RepoTools) -> None:
        """git stash creates a ref node in verbose mode with an edge to the stash commit.

        The stash ref's path is 'stash/stash@{0}' (from _collect_refs with include_stash=True).
        We look it up from graph.refs rather than hardcoding the path format.
        """
        repo.write("a.txt", "original")
        repo.commit("base")
        repo.write("a.txt", "modified — not committed")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "stash"])
        dg, _, graph = _build(str(repo.path), mode="verbose")
        src = dg.source
        # Find the stash ref in graph.refs (path contains "stash")
        stash_ref = next((r for r in graph.refs if "stash" in r.path), None)
        assert stash_ref is not None, (
            "A stash ref must appear in graph.refs in verbose mode — "
            "GitRepo._collect_refs collects stash entries when include_stash=True"
        )
        # Structural check: the stash ref node must be present in DOT
        assert node_in(src, stash_ref.path), (
            f"Stash ref node '{stash_ref.path}' must appear in DOT source in verbose mode"
        )
        # And it must edge to the stash commit SHA
        assert edge_in(src, stash_ref.path, stash_ref.commit_hexsha), (
            f"Stash ref '{stash_ref.path}' must have an edge to the stash commit"
        )

    def test_stash_not_visible_in_normal_mode(self, repo: RepoTools) -> None:
        """In normal mode, stash refs are not collected — the graph shows only the base commit."""
        repo.write("a.txt", "original")
        repo.commit("base")
        repo.write("a.txt", "modified — not committed")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "stash"])
        dg, _, graph = _build(str(repo.path), mode="normal")
        src = dg.source
        # No stash ref in graph.refs in normal mode (include_stash=False)
        stash_ref = next((r for r in graph.refs if "stash" in r.path), None)
        assert stash_ref is None, "Stash ref must not be collected by GitRepo in normal mode"
        # And "stash" must not appear as a node in the DOT graph
        assert "stash" not in src.lower(), "Stash must be absent from normal mode DOT output"


# ---------------------------------------------------------------------------
# EP 10 — Cherry-Pick
# Lesson: cherry-pick copies a commit's changes to another branch but the
#         resulting commit has a new SHA because its parent is different.
# ---------------------------------------------------------------------------


class TestLesson10CherryPick:
    def test_cherry_pick_creates_new_commit_on_target_branch(self, repo: RepoTools) -> None:
        """Cherry-picked commit gets a new SHA; its parent is the target branch tip."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("gem.txt", "the gem change")
        gem_sha = repo.commit("add gem")
        repo.write("noise.txt")
        repo.commit("noise")
        repo.checkout("main")
        repo.write("main_work.txt")
        main_sha = repo.commit("main work")
        repo._run(["git", "cherry-pick", gem_sha])
        picked_sha = repo.rev_parse("HEAD")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert picked_sha != gem_sha, "Cherry-picked commit must have a different SHA"
        assert node_in(src, picked_sha)
        assert edge_in(src, picked_sha, main_sha)

    def test_cherry_pick_conflict_shows_cherry_pick_head_in_graph(self, repo: RepoTools) -> None:
        """Fix #24: an in-progress cherry-pick conflict writes CHERRY_PICK_HEAD into the graph.

        When 'git cherry-pick' stops with a conflict, git writes .git/CHERRY_PICK_HEAD
        pointing at the commit being applied.  gitplot now surfaces this as a visible ref.
        """
        import subprocess

        repo.write("file.txt", "v1")
        repo.commit("initial")
        repo.checkout("feature", new=True)
        repo.write("file.txt", "feature version")
        feature_sha = repo.commit("feature change")
        repo.checkout("main")
        repo.write("file.txt", "main version")
        repo.commit("main diverges")
        try:
            repo._run(["git", "cherry-pick", feature_sha])
        except subprocess.CalledProcessError:
            pass  # conflict expected
        assert (repo.path / ".git" / "CHERRY_PICK_HEAD").exists()

        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "CHERRY_PICK_HEAD"), "CHERRY_PICK_HEAD must appear during conflict"
        assert edge_in(src, "CHERRY_PICK_HEAD", feature_sha)
        # DOT label accuracy: verify the label text is present in source
        assert "CHERRY_PICK_HEAD" in src

    def test_cherry_picked_and_original_commit_both_in_graph(self, repo: RepoTools) -> None:
        """Both the original commit and the cherry-picked copy coexist in the graph.

        The cherry-pick is done onto a diverged main (main has its own commit after
        the fork) so the two commits have different parents and therefore different SHAs
        even if timestamps are identical.
        """
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("gem.txt", "gem")
        gem_sha = repo.commit("gem")
        repo.checkout("main")
        # Main must diverge from base so picked_sha has a different parent than gem_sha
        repo.write("main_extra.txt")
        main_extra_sha = repo.commit("main extra work")
        repo._run(["git", "cherry-pick", gem_sha])
        picked_sha = repo.rev_parse("HEAD")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        # Different parents guarantee different SHAs
        assert gem_sha != picked_sha, (
            "Cherry-picked commit must have a different SHA: "
            "different parent commit means different commit object"
        )
        assert node_in(src, gem_sha)
        assert node_in(src, picked_sha)
        # Picked commit's parent is the main extra commit (not gem's parent)
        assert edge_in(src, picked_sha, main_extra_sha)


# ---------------------------------------------------------------------------
# EP 11 — Reflog: Git's Safety Net
# Lesson: after reset --hard the commit is unreachable from any ref, so gitplot
#         doesn't show it — but it still exists and reappears when you detach HEAD at it.
# ---------------------------------------------------------------------------


class TestLesson11Reflog:
    def test_reset_hard_leaves_orig_head_pointing_at_pre_reset_commit(
        self, repo: RepoTools
    ) -> None:
        """After reset --hard: ORIG_HEAD keeps the pre-reset commit reachable in the graph.

        Fix #24: git reset --hard writes .git/ORIG_HEAD pointing at the commit that was
        HEAD before the reset.  gitplot now reads this file and adds ORIG_HEAD as a ref node,
        so learners can see the safety net git leaves behind.
        """
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second — backed up by ORIG_HEAD")
        repo._run(["git", "reset", "--hard", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, sha1)
        # git reset --hard writes ORIG_HEAD, so sha2 stays visible via that ref
        assert node_in(src, "ORIG_HEAD")
        assert edge_in(src, "ORIG_HEAD", sha2)
        # DOT label accuracy: node label is the bare name "ORIG_HEAD"
        assert "ORIG_HEAD" in src

    def test_lost_commit_reappears_when_head_detached_at_it(self, repo: RepoTools) -> None:
        """Detaching HEAD at the 'lost' SHA makes it visible again — the object still exists."""
        repo.write("a.txt")
        repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second — will be lost")
        repo._run(["git", "reset", "--hard", "HEAD~1"])
        repo.detach(sha2)
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, sha2)
        assert edge_in(src, "HEAD", sha2)

    def test_new_branch_from_recovered_sha_makes_it_permanent(self, repo: RepoTools) -> None:
        """Creating a branch at the recovered SHA keeps it permanently reachable."""
        repo.write("a.txt")
        repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second — will be lost")
        repo._run(["git", "reset", "--hard", "HEAD~1"])
        repo._run(["git", "branch", "recover", sha2])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/heads/recover")
        assert edge_in(src, "refs/heads/recover", sha2)


# ---------------------------------------------------------------------------
# EP 13 — Tags
# Lesson: lightweight tag is a direct ref → commit (one hop); annotated tag
#         inserts a tag object between the ref and the commit (two hops).
# ---------------------------------------------------------------------------


class TestLesson13Tags:
    def test_lightweight_tag_is_direct_ref_to_commit(self, repo: RepoTools) -> None:
        """Lightweight tag: one tag node with a direct edge to the commit."""
        repo.write("a.txt")
        sha = repo.commit("release prep")
        repo.tag("v1.0", annotated=False)
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/tags/v1.0")
        assert edge_in(src, "refs/tags/v1.0", sha)

    def test_annotated_tag_creates_intermediate_tag_object(self, repo: RepoTools) -> None:
        """Annotated tag: ref → tag object → commit (two-hop chain, not one).

        The tag object node has its own SHA distinct from the commit SHA.
        We verify the full chain: refs/tags/v2.0 → tag_obj_sha → commit_sha.
        """
        repo.write("a.txt")
        sha = repo.commit("release prep")
        repo.tag("v2.0", annotated=True, message="Release 2.0")
        dg, _, graph = _build(str(repo.path))
        src = dg.source
        # Find the annotated tag ref in the graph to get the tag object SHA
        tag_ref = next((r for r in graph.refs if r.path == "refs/tags/v2.0"), None)
        assert tag_ref is not None, "refs/tags/v2.0 must appear in graph.refs"
        tag_obj_sha = tag_ref.tag_object_hexsha
        assert tag_obj_sha is not None, "Annotated tag must have a tag_object_hexsha"
        assert tag_obj_sha != sha, "Tag object SHA must differ from commit SHA"
        # Full two-hop chain must be present in the DOT source
        assert node_in(src, "refs/tags/v2.0"), "Tag ref node must exist"
        assert node_in(src, tag_obj_sha), "Tag object node must exist"
        assert node_in(src, sha), "Commit node must exist"
        assert edge_in(src, "refs/tags/v2.0", tag_obj_sha), (
            "Annotated tag ref must edge to the tag object, not the commit"
        )
        assert edge_in(src, tag_obj_sha, sha), "Tag object must edge to the commit"
        # The ref must NOT skip the tag object and point directly to the commit
        assert not edge_in(src, "refs/tags/v2.0", sha), (
            "Annotated tag ref must not point directly to the commit — it goes via a tag object"
        )

    def test_lightweight_and_annotated_tags_coexist(self, repo: RepoTools) -> None:
        """Both tag types appear simultaneously, with different graph shapes.

        v1.0 (lightweight): refs/tags/v1.0 → commit (one hop)
        v2.0 (annotated):   refs/tags/v2.0 → tag_object → commit (two hops)
        """
        repo.write("a.txt")
        sha = repo.commit("release prep")
        repo.tag("v1.0", annotated=False)
        repo.tag("v2.0", annotated=True, message="v2.0")
        dg, _, graph = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/tags/v1.0")
        assert node_in(src, "refs/tags/v2.0")
        # v1.0 points directly to the commit (one hop)
        assert edge_in(src, "refs/tags/v1.0", sha)
        # v2.0 goes via a tag object — find and verify the two-hop chain
        tag_ref = next((r for r in graph.refs if r.path == "refs/tags/v2.0"), None)
        assert tag_ref is not None
        tag_obj_sha = tag_ref.tag_object_hexsha
        assert tag_obj_sha is not None, "v2.0 must have a tag object SHA"
        assert node_in(src, tag_obj_sha), "Tag object node must be in the graph"
        assert edge_in(src, "refs/tags/v2.0", tag_obj_sha), "v2.0 ref → tag object"
        assert edge_in(src, tag_obj_sha, sha), "tag object → commit"
        # v2.0 must not point directly to the commit
        assert not edge_in(src, "refs/tags/v2.0", sha)


# ---------------------------------------------------------------------------
# EP 17 — The Object Model (verbose mode)
# Lesson: every commit points to a root tree; trees point to blobs (files)
#         and child trees (subdirectories).
# ---------------------------------------------------------------------------


class TestLesson17ObjectModel:
    def test_commit_links_to_tree_links_to_blob(self, repo: RepoTools) -> None:
        """Verbose: commit node → tree node → blob node chain is present."""
        repo.write("hello.txt", "hello world")
        sha_commit = repo.commit("initial")
        dg, _, graph = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, sha_commit)
        cd = graph.commits[sha_commit]
        assert cd.tree_hexsha is not None
        assert node_in(src, cd.tree_hexsha)
        assert edge_in(src, sha_commit, cd.tree_hexsha)

    def test_subdirectory_creates_child_tree_node(self, repo: RepoTools) -> None:
        """A subdirectory appears as a child tree node below the root tree."""
        repo.write("src/core.py", "class Core: pass")
        sha_commit = repo.commit("add src/core.py")
        dg, _, graph = _build(str(repo.path), mode="verbose")
        src_dot = dg.source
        cd = graph.commits[sha_commit]
        root_tree_sha = cd.tree_hexsha
        assert root_tree_sha is not None
        td = graph.trees.get(root_tree_sha)
        assert td is not None, "Root tree data should be populated in verbose mode"
        assert len(td.child_tree_hexshas) >= 1, "src/ directory should create a child tree"
        child_tree_sha = td.child_tree_hexshas[0]
        assert node_in(src_dot, child_tree_sha)
        assert edge_in(src_dot, root_tree_sha, child_tree_sha)

    def test_blob_label_appears_for_each_file(self, repo: RepoTools) -> None:
        """Each committed file produces a blob node in the verbose graph."""
        repo.write("README.md", "# Hello")
        repo.write("app.py", "print('hi')")
        sha_commit = repo.commit("two files")
        dg, _, graph = _build(str(repo.path), mode="verbose")
        src_dot = dg.source
        cd = graph.commits[sha_commit]
        td = graph.trees.get(cd.tree_hexsha)
        assert td is not None
        assert len(td.blob_entries) == 2
        for _name, blob_sha in td.blob_entries:
            assert node_in(src_dot, blob_sha), f"Expected blob node for SHA {blob_sha}"


# ---------------------------------------------------------------------------
# EP 18 — Content-Addressable Storage
# Lesson: an unchanged file uses the same blob SHA across commits; modified files
#         produce a new blob SHA.
# ---------------------------------------------------------------------------


class TestLesson18ContentAddressable:
    def test_unchanged_file_reuses_same_blob_sha(self, repo: RepoTools) -> None:
        """README.md blob SHA is identical in commit 1 and commit 2 when unchanged."""
        repo.write("README.md", "# unchanged content")
        repo.write("app.py", "v1")
        sha1 = repo.commit("initial")
        repo.write("app.py", "v2")  # modify only app.py
        sha2 = repo.commit("update app.py")
        dg, _, graph = _build(str(repo.path), mode="verbose")
        td1 = graph.trees.get(graph.commits[sha1].tree_hexsha)
        td2 = graph.trees.get(graph.commits[sha2].tree_hexsha)
        assert td1 is not None and td2 is not None
        readme_sha_c1 = next(h for n, h in td1.blob_entries if n == "README.md")
        readme_sha_c2 = next(h for n, h in td2.blob_entries if n == "README.md")
        assert readme_sha_c1 == readme_sha_c2, (
            "Unchanged file must share the same blob SHA across commits "
            "(content-addressable deduplication)"
        )

    def test_modified_file_produces_new_blob_sha(self, repo: RepoTools) -> None:
        """Modified file in commit 2 has a different blob SHA than in commit 1."""
        repo.write("app.py", "version 1")
        sha1 = repo.commit("initial")
        repo.write("app.py", "version 2")
        sha2 = repo.commit("update")
        dg, _, graph = _build(str(repo.path), mode="verbose")
        td1 = graph.trees.get(graph.commits[sha1].tree_hexsha)
        td2 = graph.trees.get(graph.commits[sha2].tree_hexsha)
        assert td1 is not None and td2 is not None
        app_sha_c1 = next(h for n, h in td1.blob_entries if n == "app.py")
        app_sha_c2 = next(h for n, h in td2.blob_entries if n == "app.py")
        assert app_sha_c1 != app_sha_c2, "Modified file must produce a new blob SHA"

    def test_shared_blob_node_appears_once_in_graph(self, repo: RepoTools) -> None:
        """A blob shared across commits appears as a single node (not duplicated)."""
        repo.write("README.md", "# shared")
        repo.write("app.py", "v1")
        sha1 = repo.commit("initial")
        repo.write("app.py", "v2")
        repo.commit("update")
        dg, _, graph = _build(str(repo.path), mode="verbose")
        td1 = graph.trees.get(graph.commits[sha1].tree_hexsha)
        assert td1 is not None
        readme_sha = next(h for n, h in td1.blob_entries if n == "README.md")
        # The shared blob must appear in the graph (node_in handles quoted and unquoted DOT ids)
        assert node_in(dg.source, readme_sha), "Shared blob must appear in the verbose graph"
        # Count node definitions only — not edge targets.
        # In graphviz DOT output, node statements are indented with a tab and the SHA
        # is the first token on the line (before the attribute list `[`).
        # Edge statements also start with `\t` but the SHA appears AFTER `-> `, never first.
        # So `\t{sha} [` or `\t"{sha}" [` uniquely identifies a node definition line.
        node_def_count = (
            dg.source.count(f'\t"{readme_sha}" [')  # quoted node definition
            + dg.source.count(f"\t{readme_sha} [")  # unquoted node definition
        )
        assert node_def_count == 1, (
            f"Shared blob {readme_sha[:7]} should appear as exactly one node definition; "
            f"got {node_def_count}. GraphBuilder._rendered_nodes should prevent duplicates."
        )


# ---------------------------------------------------------------------------
# EP 19 — The Staging Area Exposed
# Lesson: git add creates a blob object and puts it in the Staged Changes box;
#         unstaged changes and untracked files each get their own box.
# ---------------------------------------------------------------------------


class TestLesson19IndexExposed:
    def test_staged_file_appears_in_staged_changes_box(self, repo: RepoTools) -> None:
        """After git add: 'Staged Changes' node present with the staged filename."""
        repo.write("a.txt")
        repo.commit("base")
        repo.write("new.txt", "brand new")
        repo._run(["git", "add", "new.txt"])
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "Staged Changes")
        assert "new.txt" in src

    def test_unstaged_changes_appear_in_unstaged_box(self, repo: RepoTools) -> None:
        """Modifying a tracked file without staging shows it in 'Unstaged Changes'."""
        repo.write("a.txt", "original")
        repo.commit("base")
        repo.write("a.txt", "modified — not staged")
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "Unstaged Changes")
        assert "a.txt" in src

    def test_untracked_file_appears_in_untracked_box(self, repo: RepoTools) -> None:
        """A new file that hasn't been git-added appears in the 'Untracked' box."""
        repo.write("a.txt")
        repo.commit("base")
        repo.write("mystery.txt", "not tracked yet")
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "Untracked")
        assert "mystery.txt" in src

    def test_committed_file_clears_staged_changes(self, repo: RepoTools) -> None:
        """After git commit: Staged Changes box disappears; file appears under tree."""
        # Establish a base commit so verbose mode can render the index state
        repo.write("base.txt")
        repo.commit("base commit")
        # Stage a new file
        repo.write("new.txt", "staged content")
        repo._run(["git", "add", "new.txt"])
        # Verify staged box appears
        dg_before, _, _ = _build(str(repo.path), mode="verbose")
        assert node_in(dg_before.source, "Staged Changes")
        # Now commit — staged box should disappear
        sha = repo.commit("add new.txt")
        dg_after, _, _ = _build(str(repo.path), mode="verbose")
        src_after = dg_after.source
        assert not node_in(src_after, "Staged Changes")
        assert node_in(src_after, sha)

    def test_all_three_boxes_can_be_simultaneously_visible(self, repo: RepoTools) -> None:
        """Staged, unstaged, and untracked files can all appear at the same time."""
        repo.write("committed.txt", "committed")
        repo.commit("base")
        # unstaged: modify committed file without staging
        repo.write("committed.txt", "modified")
        # staged: add a new file
        repo.write("staged.txt", "staged")
        repo._run(["git", "add", "staged.txt"])
        # untracked: create a file without adding
        repo.write("untracked.txt", "untracked")
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "Staged Changes")
        assert node_in(src, "Unstaged Changes")
        assert node_in(src, "Untracked")

    # DOT accuracy: file nodes use "staged|path", "unstaged|path", "untracked|path" IDs
    def test_staged_file_node_id_and_edge_are_correct(self, repo: RepoTools) -> None:
        """The staged file gets node ID 'staged|<path>' with an edge from 'Staged Changes'."""
        repo.write("a.txt")
        repo.commit("base")
        repo.write("new.txt", "content")
        repo._run(["git", "add", "new.txt"])
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "staged|new.txt")
        assert edge_in(src, "Staged Changes", "staged|new.txt")

    def test_untracked_file_node_id_and_edge_are_correct(self, repo: RepoTools) -> None:
        """Untracked file gets node ID 'untracked|<path>' with an edge from 'Untracked'."""
        repo.write("a.txt")
        repo.commit("base")
        repo.write("ghost.txt", "not tracked")
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "untracked|ghost.txt")
        assert edge_in(src, "Untracked", "untracked|ghost.txt")

    def test_staged_file_visible_before_first_commit(self, repo: RepoTools) -> None:
        """Fix #23: staged file appears in verbose mode even before the first commit (unborn HEAD).

        Prior to the fix, the empty-repo guard in builder.py returned a 'no-repo' node
        before _build_index() could run.  Now it checks for index state first.
        """
        repo.write("README.md", "# Hello")
        repo._run(["git", "add", "README.md"])
        # No commit yet — unborn HEAD
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert node_in(src, "Staged Changes"), "Staged Changes box must appear before first commit"
        assert node_in(src, "staged|README.md"), "Specific file node must appear"
        assert edge_in(src, "Staged Changes", "staged|README.md")
        assert "no-repo" not in src
        assert "No git repo found" not in src


# ---------------------------------------------------------------------------
# Worktrees in branch mode (feat #25)
# Lesson: git worktree lets you check out a second branch into a separate
#         directory — branch mode annotates those branches with the path.
# ---------------------------------------------------------------------------


class TestWorktrees:
    def test_branch_without_linked_worktree_has_no_annotation(self, repo: RepoTools) -> None:
        """A branch not checked out in any worktree shows a plain label in branch mode."""
        repo.write("a.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("b.txt")
        repo.commit("feature work")
        repo.checkout("main")

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source
        assert node_in(src, "feature")
        assert "[wt:" not in src

    def test_linked_worktree_branch_label_contains_wt_path(self, repo: RepoTools) -> None:
        """A branch checked out in a linked worktree gets '[wt: <path>]' in its label.

        Feat #25: gitplot reads 'git worktree list --porcelain', skips the main worktree,
        and annotates each linked branch node with the worktree directory path.
        """
        repo.write("a.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("b.txt")
        repo.commit("feature work")
        repo.checkout("main")

        wt_path = repo.path.parent / (repo.path.name + "-wt")
        repo._run(["git", "worktree", "add", str(wt_path), "feature"])

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source
        assert node_in(src, "feature")
        # DOT label accuracy: the worktree path and annotation marker must both appear
        # git porcelain always outputs forward-slash paths (even on Windows)
        assert wt_path.as_posix() in src, "Worktree path must appear in DOT source"
        assert "[wt:" in src, "'[wt:' annotation marker must appear in DOT source"

    def test_linked_worktree_annotation_is_in_node_label_not_separate_node(
        self, repo: RepoTools
    ) -> None:
        """The worktree path is part of the branch node label, not a new node."""
        repo.write("a.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("b.txt")
        repo.commit("feature work")
        repo.checkout("main")

        wt_path = repo.path.parent / (repo.path.name + "-wt")
        repo._run(["git", "worktree", "add", str(wt_path), "feature"])

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source
        # The path must appear inside a node label (surrounded by label=" ... ")
        # rather than as a standalone token that would indicate a new node.
        # git porcelain always uses forward slashes (even on Windows)
        wt_str = wt_path.as_posix()
        assert wt_str in src
        # Confirm the branch node itself still exists with the right ID
        assert node_in(src, "feature")
        # Confirm no second node was created for the path alone
        assert f"\t{wt_str} [" not in src and f'\t"{wt_str}" [' not in src

    def test_main_worktree_branch_has_no_wt_annotation(self, repo: RepoTools) -> None:
        """The branch checked out in the main worktree is not annotated — only linked ones are."""
        repo.write("a.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("b.txt")
        repo.commit("feature work")
        repo.checkout("main")

        wt_path = repo.path.parent / (repo.path.name + "-wt")
        repo._run(["git", "worktree", "add", str(wt_path), "feature"])

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source
        # 'main' is in the main worktree — its label should be "HEAD->main", no [wt:...]
        assert "HEAD->main" in src
        assert "HEAD->main\n[wt:" not in src


# ---------------------------------------------------------------------------
# EP 08 — Interactive Rebase
# Lesson: interactive rebase lets you squash, drop, or reorder commits before
#         sharing history.  The resulting commits get new SHAs; ORIG_HEAD records
#         where the branch was before the rebase as a safety net.
# ---------------------------------------------------------------------------


class TestLesson08InteractiveRebase:
    def test_squash_collapses_two_commits_into_one(self, repo: RepoTools) -> None:
        """After squash: one commit replaces two; main no longer reaches old SHAs directly.

        Simulated with git reset --soft + commit, which produces the same graph topology
        as an interactive rebase squash (one new commit whose parent is the base).
        """
        repo.write("base.txt")
        sha_base = repo.commit("base")
        repo.write("a.txt")
        repo.commit("commit A")
        repo.write("b.txt")
        repo.commit("commit B")

        # Simulate squash: collapse both A and B into one new commit on top of base
        repo._run(["git", "reset", "--soft", sha_base])
        squash_sha = repo.commit("squashed: A + B")

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        # main points at the single squashed commit
        assert node_in(src, squash_sha)
        assert edge_in(src, "refs/heads/main", squash_sha)
        # squashed commit's parent is the base (not the intermediate A or B)
        assert edge_in(src, squash_sha, sha_base)

    def test_orig_head_after_squash_tracks_pre_squash_tip(self, repo: RepoTools) -> None:
        """After squash: ORIG_HEAD points at the old tip, keeping discarded SHAs visible.

        git reset --soft (which backs the branch pointer up before replaying) writes
        ORIG_HEAD to the pre-reset HEAD commit.  This is the same file interactive
        rebase writes, giving learners a visible safety net in the graph.
        """
        repo.write("base.txt")
        sha_base = repo.commit("base")
        repo.write("a.txt")
        sha_a = repo.commit("commit A")
        repo.write("b.txt")
        sha_b = repo.commit("commit B")

        repo._run(["git", "reset", "--soft", sha_base])
        repo.commit("squashed: A + B")

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        # ORIG_HEAD is written by git reset; it keeps sha_b visible
        assert node_in(src, "ORIG_HEAD"), "ORIG_HEAD must appear after a squash-style reset"
        assert edge_in(src, "ORIG_HEAD", sha_b), "ORIG_HEAD must point at the pre-squash tip"
        # sha_b -> sha_a chain is still reachable via ORIG_HEAD
        assert node_in(src, sha_b)
        assert node_in(src, sha_a)
        assert edge_in(src, sha_b, sha_a)

    def test_dropped_commit_is_unreachable_but_orig_head_preserves_it(
        self, repo: RepoTools
    ) -> None:
        """After drop: the commit is unreachable from main but visible via ORIG_HEAD.

        Interactive rebase 'drop' is simulated by resetting the branch before the
        commit — the same graph effect: dropped SHA is gone from the main chain.
        """
        repo.write("a.txt")
        sha_a = repo.commit("commit A — will be kept")
        repo.write("b.txt")
        sha_b = repo.commit("commit B — will be dropped")

        # Drop sha_b by hard-resetting to sha_a
        repo._run(["git", "reset", "--hard", sha_a])

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        # sha_b is not pointed to by main
        assert not edge_in(src, "refs/heads/main", sha_b)
        # sha_a is the new main tip
        assert edge_in(src, "refs/heads/main", sha_a)
        # ORIG_HEAD makes sha_b visible in the graph (safety net)
        assert node_in(src, "ORIG_HEAD")
        assert edge_in(src, "ORIG_HEAD", sha_b)
        assert node_in(src, sha_b)

    def test_rebase_gives_new_sha_and_linear_parent_chain(self, repo: RepoTools) -> None:
        """After rebase: replayed commits have new SHAs; parent is the new base.

        This is the core EP08 lesson: old SHA is gone from the branch ref, new SHA
        appears with the new base as parent, and ORIG_HEAD preserves the old tip.
        """
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        old_sha = repo.commit("feature work")
        repo.checkout("main")
        repo.write("main_extra.txt")
        new_base_sha = repo.commit("main extra work")

        repo.checkout("feature")
        repo._run(["git", "rebase", "main"])
        new_sha = repo.rev_parse("HEAD")

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        # Rebased commit has a different SHA
        assert new_sha != old_sha, "Rebase must produce a new SHA"
        # New SHA is present; parent is main's new tip
        assert node_in(src, new_sha)
        assert edge_in(src, new_sha, new_base_sha)
        # Old SHA is no longer pointed to by refs/heads/feature
        assert not edge_in(src, "refs/heads/feature", old_sha)
        # ORIG_HEAD keeps the old tip visible
        assert node_in(src, "ORIG_HEAD")
        assert edge_in(src, "ORIG_HEAD", old_sha)


# ---------------------------------------------------------------------------
# EP 12 — Comparing --no-ff Merge vs Rebase in Branch Mode
# Lesson: branch mode highlights the structural difference between strategies:
#         --no-ff preserves a fork point (branches visibly diverged then converged);
#         rebase produces a linear parent-child chain with no fork node at all.
# ---------------------------------------------------------------------------


class TestLesson12MergeVsRebaseBranchMode:
    def _diverged_repo(self, repo: RepoTools) -> tuple[str, str]:
        """Build a repo where main and feature have each added one commit after branching."""
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        feature_sha = repo.commit("feature work")
        repo.checkout("main")
        repo.write("main_extra.txt")
        main_sha = repo.commit("main extra work")
        return feature_sha, main_sha

    def test_diverged_branches_show_fork_node_in_branch_mode(self, repo: RepoTools) -> None:
        """Before any merge or rebase: two branches that have each advanced produce a fork
        commit node in branch mode at their common ancestor.

        Edge pattern: fork_sha -> main AND fork_sha -> feature (fork is parent of both,
        in RL layout the fork sits to the right of both branch labels).
        """
        self._diverged_repo(repo)

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source

        assert node_in(src, "main")
        assert node_in(src, "feature")
        # Fork node label uses actual newline (graphviz Python lib renders \n as chr(10))
        assert '"fork\n' in src, (
            'Diverged branches must produce a fork commit node labelled "fork\\n<sha>"'
        )
        fork_shas = _fork_sha_labels(src)
        assert fork_shas, "At least one fork SHA must be extractable"
        fork_sha = fork_shas[0]
        # Fork is parent of both branches: fork -> main AND fork -> feature
        assert edge_in(src, fork_sha, "main"), "Fork must have an edge to main"
        assert edge_in(src, fork_sha, "feature"), "Fork must have an edge to feature"

    def test_no_ff_merge_retains_fork_node_in_branch_mode(self, repo: RepoTools) -> None:
        """After --no-ff merge (feature branch kept): the fork node still appears.

        --no-ff preserves the knowledge that the branches diverged at a real commit.
        The topology is unchanged: fork -> main AND fork -> feature.  This is the
        key EP12 contrast with rebase, which produces a linear chain instead.
        """
        self._diverged_repo(repo)
        repo.merge("feature", no_ff=True)

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source

        assert node_in(src, "main")
        assert node_in(src, "feature")
        assert '"fork\n' in src, (
            "After --no-ff merge (feature kept), fork node must still appear in branch mode"
        )
        fork_shas = _fork_sha_labels(src)
        assert fork_shas, "Fork SHA must be extractable after --no-ff merge"
        fork_sha = fork_shas[0]
        assert edge_in(src, fork_sha, "main"), "Fork -> main edge must exist"
        assert edge_in(src, fork_sha, "feature"), "Fork -> feature edge must exist"

    def test_rebase_produces_linear_chain_in_branch_mode(self, repo: RepoTools) -> None:
        """After rebase: feature's tip sits directly above main — the topology becomes
        a linear chain rather than a symmetric fork.

        The fork commit that appears IS main's tip (feature is now its direct child).
        Edge pattern: main -> fork_sha -> feature (main points to the fork, fork points
        to feature — the opposite of the pre-rebase pattern where fork pointed to main).
        """
        self._diverged_repo(repo)
        repo.checkout("feature")
        repo._run(["git", "rebase", "main"])
        repo.checkout("main")

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source

        assert node_in(src, "main")
        assert node_in(src, "feature")
        # A fork commit still appears — it is now main's tip (not the old common base)
        assert '"fork\n' in src, "A fork commit node must still appear after rebase"
        fork_shas = _fork_sha_labels(src)
        assert fork_shas, "Fork SHA must be extractable after rebase"
        fork_sha = fork_shas[0]
        # Linear chain: main -> fork -> feature  (not: fork -> main AND fork -> feature)
        assert edge_in(src, "main", fork_sha), (
            "After rebase, main must point TO the fork commit (main's tip IS the fork)"
        )
        assert edge_in(src, fork_sha, "feature"), (
            "After rebase, the fork must point to feature (feature branches above main)"
        )
        # The pre-rebase symmetric pattern (fork -> main) must be gone
        assert not edge_in(src, fork_sha, "main"), (
            "After rebase, the fork must NOT point back to main — that was the pre-rebase pattern"
        )

    def test_fast_forward_merge_leaves_no_fork_in_branch_mode(self, repo: RepoTools) -> None:
        """After a fast-forward merge: main advances to feature's tip; no fork ever formed.

        Branch mode shows a direct main -> feature edge (main is the parent, feature is the
        child because it was ahead of main and main caught up).  No fork commit node appears.
        """
        repo.write("base.txt")
        repo.commit("base")
        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        repo.commit("feature work")
        repo.checkout("main")
        repo._run(["git", "merge", "feature"])  # fast-forward

        dg, _, _ = _build(str(repo.path), mode="branch")
        src = dg.source

        # No fork — they were never diverged
        assert '"fork\n' not in src, (
            "Fast-forward merge never creates a fork commit — no fork node should appear"
        )
        assert node_in(src, "main")
        assert node_in(src, "feature")
        # After FF, the two branches are connected by a direct edge (no fork in between)
        assert edge_in(src, "main", "feature") or edge_in(src, "feature", "main"), (
            "After fast-forward merge, main and feature must be directly connected"
        )


# EP 14 — Remote fork workflow
# Lesson: pushing creates remote tracking refs (refs/remotes/origin/*) that appear
#         in the graph; local and remote diverge when the local branch advances past
#         the last push; exclude_remotes hides all remote tracking refs.
# ---------------------------------------------------------------------------


class TestLesson14RemoteFork:
    def _setup_remote(self, repo: RepoTools) -> None:
        """Create a bare remote unique to this test's tmp dir, add as origin, push main."""
        remote_path = repo.path.parent / (repo.path.name + "_remote.git")
        subprocess.check_call(
            ["git", "init", "--bare", str(remote_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        repo._run(["git", "remote", "add", "origin", str(remote_path)])
        repo._run(["git", "push", "-u", "origin", "main"])

    def test_remote_tracking_ref_appears_after_push(self, repo: RepoTools) -> None:
        """After pushing, refs/remotes/origin/main appears as a node pointing at the commit."""
        repo.write("a.txt")
        sha1 = repo.commit("initial")
        self._setup_remote(repo)

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert node_in(src, "refs/remotes/origin/main"), (
            "refs/remotes/origin/main must appear as a node after push"
        )
        assert edge_in(src, "refs/remotes/origin/main", sha1), (
            "refs/remotes/origin/main must edge to the pushed commit SHA"
        )

    def test_local_and_remote_tracking_ref_diverge_after_local_commit(
        self, repo: RepoTools
    ) -> None:
        """After a local commit past the last push, local and remote diverge."""
        repo.write("a.txt")
        sha1 = repo.commit("initial")
        self._setup_remote(repo)

        repo.write("b.txt")
        sha2 = repo.commit("local-only")

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        # local branch has advanced to sha2
        assert edge_in(src, "refs/heads/main", sha2), (
            "refs/heads/main must point to the new local commit after divergence"
        )
        # remote tracking ref still points to the last-pushed commit
        assert node_in(src, "refs/remotes/origin/main"), (
            "refs/remotes/origin/main must still appear after local divergence"
        )
        assert edge_in(src, "refs/remotes/origin/main", sha1), (
            "refs/remotes/origin/main must point to the pre-divergence pushed commit"
        )

    def test_pushed_feature_branch_shows_remote_ref(self, repo: RepoTools) -> None:
        """After pushing a feature branch, both local and remote tracking refs appear."""
        repo.write("a.txt")
        repo.commit("initial")
        self._setup_remote(repo)

        repo.checkout("feature", new=True)
        repo.write("feat.txt")
        sha_feat = repo.commit("feature work")
        repo._run(["git", "push", "-u", "origin", "feature"])

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert node_in(src, "refs/heads/feature"), "Local refs/heads/feature must appear after push"
        assert node_in(src, "refs/remotes/origin/feature"), (
            "refs/remotes/origin/feature must appear after push"
        )
        assert edge_in(src, "refs/heads/feature", sha_feat), (
            "Local feature ref must point to the feature commit"
        )
        assert edge_in(src, "refs/remotes/origin/feature", sha_feat), (
            "Remote tracking ref must point to the same feature commit"
        )

    def test_remote_refs_hidden_with_exclude_remotes(self, repo: RepoTools) -> None:
        """With exclude_remotes=True, no refs/remotes/* nodes appear; local refs survive."""
        repo.write("a.txt")
        repo.commit("initial")
        self._setup_remote(repo)

        dg, _, _ = _build(str(repo.path), exclude_remotes=True)
        src = dg.source

        assert "refs/remotes" not in src, (
            "With exclude_remotes=True, no refs/remotes/* nodes should appear"
        )
        assert node_in(src, "refs/heads/main"), (
            "Local refs/heads/main must still appear when remotes are excluded"
        )


# EP 15 — git bisect and the Commit Graph
# Lesson: during an active bisect session git writes .git/BISECT_HEAD pointing
#         at the commit currently under test; gitplot surfaces it as a ref node
#         so learners can see exactly where bisect has landed in the history.
# ---------------------------------------------------------------------------


class TestLesson15Bisect:
    def _linear_repo(self, repo: RepoTools) -> tuple[str, str, str]:
        """Three-commit linear history: sha1 (good) < sha2 (midpoint) < sha3 (bad)."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second")
        repo.write("c.txt")
        sha3 = repo.commit("third")
        return sha1, sha2, sha3

    def test_bisect_head_appears_during_bisect_session(self, repo: RepoTools) -> None:
        """After git bisect start --no-checkout + marking good/bad, BISECT_HEAD appears."""
        sha1, sha2, sha3 = self._linear_repo(repo)
        repo._run(["git", "bisect", "start", "--no-checkout"])
        repo._run(["git", "bisect", "bad", sha3])
        repo._run(["git", "bisect", "good", sha1])

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert node_in(src, "BISECT_HEAD"), (
            "BISECT_HEAD must appear as a ref node during an active bisect session"
        )
        assert edge_in(src, "BISECT_HEAD", sha2), (
            "BISECT_HEAD must edge to the midpoint commit git bisect selected"
        )

    def test_bisect_head_absent_when_not_bisecting(self, repo: RepoTools) -> None:
        """Without an active bisect session, no BISECT_HEAD node appears."""
        self._linear_repo(repo)

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert not node_in(src, "BISECT_HEAD"), (
            "BISECT_HEAD must not appear when no bisect session is in progress"
        )

    def test_bisect_head_malformed_does_not_crash(self, repo: RepoTools) -> None:
        """A garbage .git/BISECT_HEAD file is silently ignored; no phantom node."""
        self._linear_repo(repo)
        (repo.path / ".git" / "BISECT_HEAD").write_text("not-a-valid-sha\n", encoding="utf-8")

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert not node_in(src, "BISECT_HEAD"), (
            "A malformed BISECT_HEAD file must be silently ignored -- no phantom node"
        )

    def test_bisect_good_bad_marks_visible_alongside_bisect_head(self, repo: RepoTools) -> None:
        """In --no-checkout mode HEAD stays on main while BISECT_HEAD marks the midpoint."""
        sha1, sha2, sha3 = self._linear_repo(repo)
        repo._run(["git", "bisect", "start", "--no-checkout"])
        repo._run(["git", "bisect", "bad", sha3])
        repo._run(["git", "bisect", "good", sha1])

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert node_in(src, "BISECT_HEAD"), "BISECT_HEAD must appear"
        assert node_in(src, "refs/heads/main"), "main branch ref must still appear"
        assert edge_in(src, "refs/heads/main", sha3), (
            "main must still point at sha3 -- HEAD did not move in --no-checkout mode"
        )
        assert edge_in(src, "BISECT_HEAD", sha2), (
            "BISECT_HEAD must point at the midpoint between good sha1 and bad sha3"
        )


# EP 16 — git submodules (gitlink entries in verbose mode)
# Lesson: a submodule is stored as a mode-160000 gitlink entry in the parent tree.
#         In verbose mode gitplot must render gitlink entries as distinct nodes
#         (not blobs) so learners can see the pointer into the submodule's history.
# ---------------------------------------------------------------------------


class TestLesson16Submodules:
    def _setup_with_submodule(self, repo: RepoTools) -> tuple[str, str]:
        """Create a bare-enough subrepo, add it as a submodule, commit.

        Returns (tree_sha, sub_commit_sha) — the root tree of the parent commit
        and the commit SHA the gitlink points at.
        """
        sub_path = repo.path.parent / (repo.path.name + "_sub")
        subprocess.check_call(
            ["git", "init", "-b", "main", str(sub_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["git", "config", "user.email", "sub@test"], cwd=sub_path, stderr=subprocess.DEVNULL
        )
        subprocess.check_call(
            ["git", "config", "user.name", "Sub"], cwd=sub_path, stderr=subprocess.DEVNULL
        )
        (sub_path / "sub.txt").write_text("sub content", encoding="utf-8")
        subprocess.check_call(["git", "add", "-A"], cwd=sub_path, stderr=subprocess.DEVNULL)
        subprocess.check_call(
            ["git", "commit", "-m", "sub init"], cwd=sub_path, stderr=subprocess.DEVNULL
        )
        sub_commit_sha = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=sub_path, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )

        # Stage a regular file, add the submodule, then commit everything together
        repo.write("main.txt")
        repo._run(["git", "add", "main.txt"])
        repo._run(
            [
                "git",
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                sub_path.as_posix(),
                "lib",
            ]
        )
        repo._run(["git", "commit", "-m", "add submodule"])
        tree_sha = repo._run(["git", "rev-parse", "HEAD^{tree}"])

        return tree_sha, sub_commit_sha

    def test_submodule_gitlink_does_not_crash_verbose_build(self, repo: RepoTools) -> None:
        """Verbose build on a repo with a submodule must not raise."""
        self._setup_with_submodule(repo)

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        assert node_in(src, "HEAD")
        assert node_in(src, "refs/heads/main")

    def test_gitlink_entry_appears_as_distinct_node_in_verbose_mode(self, repo: RepoTools) -> None:
        """The submodule tree entry appears as a gitlink node, not a blob."""
        _, sub_commit_sha = self._setup_with_submodule(repo)

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        gitlink_node_id = f"gitlink|{sub_commit_sha}"
        assert node_in(src, gitlink_node_id), (
            "Submodule entry must appear as a gitlink node with ID gitlink|<sha>"
        )
        assert '"gitlink\n' in src, (
            "Gitlink node label must start with 'gitlink' to distinguish it from blobs"
        )

    def test_gitlink_edge_from_tree_to_submodule_node(self, repo: RepoTools) -> None:
        """The parent tree must have an edge to the gitlink node."""
        tree_sha, sub_commit_sha = self._setup_with_submodule(repo)

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        gitlink_node_id = f"gitlink|{sub_commit_sha}"
        assert edge_in(src, tree_sha, gitlink_node_id), (
            "Root tree node must have an edge to the gitlink node"
        )

    def test_non_submodule_blobs_still_render_alongside_gitlink(self, repo: RepoTools) -> None:
        """Regular blobs in the same commit still appear correctly alongside the gitlink."""
        _, sub_commit_sha = self._setup_with_submodule(repo)

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        gitlink_node_id = f"gitlink|{sub_commit_sha}"
        assert node_in(src, gitlink_node_id), "Gitlink node must appear"
        assert '"blob\n' in src, "Regular blob nodes must still appear alongside the gitlink node"


# EP 16 (curriculum) — Force Push Is Destroying Someone's History: Here's the Proof
# Lesson: gitplot makes the danger concrete by showing local main and origin/main
#         pointing to different commits (diverged state). After a force push,
#         origin/main resets to the local commit; the displaced commit is orphaned.
# ---------------------------------------------------------------------------


class TestEP16ForcePush:
    def _setup_diverged(self, repo: RepoTools):
        """Build the diverged state and return (sha_local, sha_teammate, clone_path).

        1. Create a bare remote unique to this test's tmp dir.
        2. Push sha_base from the main repo.
        3. Clone to clone_path; teammate adds a commit and pushes (sha_teammate).
        4. Main repo fetches: origin/main -> sha_teammate.
        5. Main repo adds a local commit: main -> sha_local, origin/main -> sha_teammate.
        """
        remote_path = repo.path.parent / (repo.path.name + "_remote.git")
        clone_path = repo.path.parent / (repo.path.name + "_clone")
        subprocess.check_call(
            ["git", "init", "--bare", "-b", "main", str(remote_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        repo.write("base.txt")
        repo.commit("base")
        repo._run(["git", "remote", "add", "origin", str(remote_path)])
        repo._run(["git", "push", "-u", "origin", "main"])

        subprocess.check_call(
            ["git", "clone", "--branch", "main", str(remote_path), str(clone_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["git", "config", "user.email", "tm@test"], cwd=clone_path, stderr=subprocess.DEVNULL
        )
        subprocess.check_call(
            ["git", "config", "user.name", "Teammate"], cwd=clone_path, stderr=subprocess.DEVNULL
        )
        (clone_path / "teammate.txt").write_text("teammate work", encoding="utf-8")
        subprocess.check_call(["git", "add", "-A"], cwd=clone_path, stderr=subprocess.DEVNULL)
        subprocess.check_call(
            ["git", "commit", "-m", "teammate commit"], cwd=clone_path, stderr=subprocess.DEVNULL
        )
        subprocess.check_call(
            ["git", "push", "origin", "main"],
            cwd=clone_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        sha_teammate = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=clone_path, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )

        repo._run(["git", "fetch", "origin"])
        repo.write("local.txt")
        sha_local = repo.commit("local-only commit")

        return sha_local, sha_teammate, clone_path

    def test_diverged_state_shows_both_refs(self, repo: RepoTools) -> None:
        """Before force push: local main and origin/main point to different commits."""
        sha_local, sha_teammate, _ = self._setup_diverged(repo)

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert edge_in(src, "refs/heads/main", sha_local), (
            "refs/heads/main must point to the local commit"
        )
        assert node_in(src, "refs/remotes/origin/main"), (
            "refs/remotes/origin/main must appear -- diverged state is visible in gitplot"
        )
        assert edge_in(src, "refs/remotes/origin/main", sha_teammate), (
            "refs/remotes/origin/main must point to the teammate's commit, not the local one"
        )

    def test_force_push_resets_origin_main(self, repo: RepoTools) -> None:
        """After force push, origin/main moves to the local commit; teammate's commit orphaned."""
        sha_local, sha_teammate, _ = self._setup_diverged(repo)
        repo._run(["git", "push", "--force", "origin", "main"])

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert edge_in(src, "refs/heads/main", sha_local), (
            "refs/heads/main must still point to sha_local after force push"
        )
        assert edge_in(src, "refs/remotes/origin/main", sha_local), (
            "After force push, refs/remotes/origin/main must point to sha_local"
        )
        assert not edge_in(src, "refs/remotes/origin/main", sha_teammate), (
            "origin/main must no longer point to the teammate's commit after force push"
        )

    def test_force_with_lease_rejected_leaves_graph_unchanged(self, repo: RepoTools) -> None:
        """Rejected --force-with-lease leaves origin/main pointing at the last-fetched SHA."""
        sha_local, sha_teammate, clone_path = self._setup_diverged(repo)

        # Teammate pushes again AFTER our last fetch -- remote has moved past sha_teammate.
        (clone_path / "more.txt").write_text("more work", encoding="utf-8")
        subprocess.check_call(["git", "add", "-A"], cwd=clone_path, stderr=subprocess.DEVNULL)
        subprocess.check_call(
            ["git", "commit", "-m", "another teammate commit"],
            cwd=clone_path,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            ["git", "push", "origin", "main"],
            cwd=clone_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        result = subprocess.run(
            ["git", "push", "--force-with-lease", "origin", "main"],
            cwd=str(repo.path),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "force-with-lease must fail when remote has moved past the last-fetched ref"
        )

        dg, _, _ = _build(str(repo.path))
        src = dg.source

        assert edge_in(src, "refs/remotes/origin/main", sha_teammate), (
            "After rejected force-with-lease, origin/main must still point to the last-fetched SHA"
        )
        assert edge_in(src, "refs/heads/main", sha_local), (
            "Local main must be unchanged after a rejected force-with-lease push"
        )

    def test_exclude_remotes_hides_origin_main_when_diverged(self, repo: RepoTools) -> None:
        """With exclude_remotes=True, origin/main is hidden even in the diverged state."""
        self._setup_diverged(repo)

        dg, _, _ = _build(str(repo.path), exclude_remotes=True)
        src = dg.source

        assert "refs/remotes" not in src, (
            "With exclude_remotes=True, no refs/remotes/* nodes should appear"
        )
        assert node_in(src, "refs/heads/main"), (
            "Local refs/heads/main must still appear when remotes are excluded"
        )


# EP 20 (curriculum) — All the Way Down: git cat-file, .git/objects, and Pack Files
# Lesson: gitplot's verbose graph SHA labels correspond directly to what git cat-file
#         reports for each object. After git gc packs loose objects, GitPython reads
#         the pack transparently and gitplot continues to show the full object graph.
# ---------------------------------------------------------------------------


class TestLesson20PackFiles:
    def test_blob_sha_matches_object_store(self, repo: RepoTools) -> None:
        """The blob SHA in verbose mode matches what git cat-file -t reports as 'blob'."""
        repo.write("hello.txt", content="hello world\n")
        repo.commit("initial")
        blob_sha = repo._run(["git", "rev-parse", "HEAD:hello.txt"])

        obj_type = subprocess.check_output(
            ["git", "cat-file", "-t", blob_sha],
            cwd=str(repo.path),
            text=True,
        ).strip()
        assert obj_type == "blob"

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        assert node_in(src, blob_sha), (
            "The blob SHA reported by git cat-file must appear as a node in the verbose graph"
        )

    def test_tree_sha_matches_object_store(self, repo: RepoTools) -> None:
        """The root tree SHA in verbose mode matches git rev-parse HEAD^{tree}."""
        repo.write("a.txt")
        repo.commit("initial")
        tree_sha = repo._run(["git", "rev-parse", "HEAD^{tree}"])

        obj_type = subprocess.check_output(
            ["git", "cat-file", "-t", tree_sha],
            cwd=str(repo.path),
            text=True,
        ).strip()
        assert obj_type == "tree"

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        assert node_in(src, tree_sha), (
            "The root tree SHA from git rev-parse HEAD^{tree} must appear in the verbose graph"
        )

    def test_verbose_mode_after_git_gc(self, repo: RepoTools) -> None:
        """After git gc packs loose objects, verbose mode still shows the full object graph."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second")

        repo._run(["git", "gc", "--quiet"])

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        assert node_in(src, sha2), (
            "Most recent commit node must still appear in verbose mode after git gc"
        )
        assert node_in(src, sha1), (
            "Earlier commit node must still appear after git gc packs the object store"
        )
        assert '"blob\n' in src, "Blob nodes must still appear in verbose mode after gc"

    def test_shared_blob_appears_once_after_git_gc(self, repo: RepoTools) -> None:
        """An unchanged file is one blob across two commits; git gc preserves deduplication."""
        repo.write("unchanged.txt", content="same content\n")
        repo.write("changing.txt", content="version 1\n")
        repo.commit("first")

        repo.write("changing.txt", content="version 2\n")
        repo.commit("second")

        blob_sha_before = repo._run(["git", "rev-parse", "HEAD~1:unchanged.txt"])
        blob_sha_after = repo._run(["git", "rev-parse", "HEAD:unchanged.txt"])
        assert blob_sha_before == blob_sha_after, (
            "unchanged.txt must have the same blob SHA in both commits"
        )
        tree_sha_1 = repo._run(["git", "rev-parse", "HEAD~1^{tree}"])
        tree_sha_2 = repo._run(["git", "rev-parse", "HEAD^{tree}"])

        repo._run(["git", "gc", "--quiet"])

        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source

        assert node_in(src, blob_sha_before), (
            "The shared blob must appear as a node in the verbose graph after gc"
        )
        assert edge_in(src, tree_sha_1, blob_sha_before), (
            "First commit's tree must have an edge to the shared blob after gc"
        )
        assert edge_in(src, tree_sha_2, blob_sha_before), (
            "Second commit's tree must also edge to the same shared blob node after gc"
        )
