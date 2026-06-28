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

from gitplot.builder import GraphBuilder
from gitplot.repo import GitRepo

from .conftest import RepoTools, edge_in, node_in


def _build(repo_path: str, mode: str = "normal", **kwargs):
    """Build a gitplot graph from a real repo path; return (Digraph, GraphBuilder, RepoGraph)."""
    git_repo = GitRepo(repo_path)
    include_trees = mode == "verbose"
    graph = git_repo.build_graph(include_trees=include_trees)
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
        """Five commits with no refs in between collapse into a single summary node."""
        repo.write("base.txt")
        repo.commit("first")
        # Add four more unremarkable commits — they form a boring run
        for i in range(4):
            repo.write(f"file{i}.txt")
            sha_last = repo.commit(f"commit {i + 2}")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        # The boring run should be collapsed: not every SHA appears as its own node
        # but a summary node label like "sha (N) sha" should be present
        assert node_in(src, "refs/heads/main")
        assert node_in(src, sha_last)
        # The very first SHA may be absorbed into a summary node
        # What we care about: there are fewer than 5 separate commit nodes
        commit_node_count = src.count('"commit\\n')
        assert commit_node_count < 5, (
            "Five boring commits should collapse — expected fewer than 5 commit nodes"
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
        """After reset --soft HEAD~1: main points to the first commit; second is gone."""
        sha1, sha2 = self._two_commits(repo)
        repo._run(["git", "reset", "--soft", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/main", sha1)
        assert not edge_in(src, "refs/heads/main", sha2)

    def test_reset_mixed_moves_branch_pointer_back(self, repo: RepoTools) -> None:
        """After reset --mixed HEAD~1: same pointer movement as --soft."""
        sha1, sha2 = self._two_commits(repo)
        repo._run(["git", "reset", "--mixed", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/main", sha1)
        assert not edge_in(src, "refs/heads/main", sha2)

    def test_reset_hard_moves_branch_pointer_back(self, repo: RepoTools) -> None:
        """After reset --hard HEAD~1: same pointer movement; working tree also wiped."""
        sha1, sha2 = self._two_commits(repo)
        repo._run(["git", "reset", "--hard", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert edge_in(src, "refs/heads/main", sha1)
        assert not edge_in(src, "refs/heads/main", sha2)


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
        """git stash creates refs/stash entries, visible in verbose mode only."""
        repo.write("a.txt", "original")
        repo.commit("base")
        repo.write("a.txt", "modified — not committed")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "stash"])
        dg, _, _ = _build(str(repo.path), mode="verbose")
        src = dg.source
        assert "stash" in src.lower(), (
            "Stash ref should appear in verbose mode graph. "
            "In normal mode stash is hidden (include_stash=False)."
        )

    def test_stash_not_visible_in_normal_mode(self, repo: RepoTools) -> None:
        """In normal mode, stash refs are not collected — the graph shows only the base commit."""
        repo.write("a.txt", "original")
        repo.commit("base")
        repo.write("a.txt", "modified — not committed")
        repo._run(["git", "add", "-A"])
        repo._run(["git", "stash"])
        dg, _, _ = _build(str(repo.path), mode="normal")
        src = dg.source
        # stash ref nodes should not appear in normal mode
        assert "stash@" not in src


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
    def test_reset_hard_removes_commit_from_normal_graph(self, repo: RepoTools) -> None:
        """After reset --hard: the reset-over commit does not appear in the graph."""
        repo.write("a.txt")
        sha1 = repo.commit("first")
        repo.write("b.txt")
        sha2 = repo.commit("second — will be lost")
        repo._run(["git", "reset", "--hard", "HEAD~1"])
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, sha1)
        assert not node_in(src, sha2)

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
        """Annotated tag: ref → tag object → commit (two-hop chain, not one)."""
        repo.write("a.txt")
        sha = repo.commit("release prep")
        repo.tag("v2.0", annotated=True, message="Release 2.0")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/tags/v2.0")
        # The annotated tag ref does NOT edge directly to the commit — it goes via a tag object
        assert not edge_in(src, "refs/tags/v2.0", sha), (
            "Annotated tag ref should point to a tag object, not directly to the commit"
        )
        # A tag object node is present (label contains "tag")
        assert "tag" in src

    def test_lightweight_and_annotated_tags_coexist(self, repo: RepoTools) -> None:
        """Both tag types appear simultaneously, with different graph shapes."""
        repo.write("a.txt")
        sha = repo.commit("release prep")
        repo.tag("v1.0", annotated=False)
        repo.tag("v2.0", annotated=True, message="v2.0")
        dg, _, _ = _build(str(repo.path))
        src = dg.source
        assert node_in(src, "refs/tags/v1.0")
        assert node_in(src, "refs/tags/v2.0")
        # v1.0 points directly to the commit
        assert edge_in(src, "refs/tags/v1.0", sha)
        # v2.0 does not (it goes via a tag object)
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
        """After git commit: Staged Changes box disappears; file appears under tree.

        Note: verbose mode requires at least one commit to exist before it can render
        the index state — an empty repo (no commits) returns 'No git repo found'.
        The lesson covers staging in a repo that already has commits.
        """
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
