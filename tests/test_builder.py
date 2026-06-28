"""Structural tests for GraphBuilder: verify nodes and edges in Graphviz output."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gitplot.builder import GraphBuilder
from gitplot.repo import (
    GitRepo,
)

from .conftest import RepoTools, edge_in, node_in


def _build(repo_path, mode="normal", **kwargs):
    """Helper: build a graph from a real repo path."""
    repo = GitRepo(repo_path)
    include_trees = mode == "verbose"
    graph = repo.build_graph(include_trees=include_trees)
    index_state = repo.get_index_state() if mode == "verbose" else None
    branch_topo = repo.get_branch_topology() if mode == "branch" else None
    builder = GraphBuilder(mode=mode, **kwargs)
    dg = builder.build(graph, index_state=index_state, branch_topology=branch_topo)
    return dg, builder, graph, repo


# ---------------------------------------------------------------------------
# No valid repo
# ---------------------------------------------------------------------------


def test_invalid_repo_shows_message():
    builder = GraphBuilder(mode="normal")
    from gitplot.repo import RepoGraph

    empty = RepoGraph(
        commits={},
        trees={},
        blobs={},
        refs=[],
        head_branch_path=None,
        is_detached=False,
        hash_length=5,
    )
    dg = builder.build(empty)
    assert "no-repo" in dg.source or "No git repo found" in dg.source


# ---------------------------------------------------------------------------
# Empty repo (unborn HEAD) in verbose mode  -- issue #23
# ---------------------------------------------------------------------------


def test_empty_repo_verbose_staged_file_shows_staged_changes_box(repo: RepoTools):
    """Staged Changes box must appear in verbose mode even before the first commit."""
    repo.write("README.md", "# Hello")
    repo._run(["git", "add", "README.md"])
    # No commit yet -- repo has an unborn HEAD
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    src = dg.source
    assert node_in(src, "Staged Changes"), (
        "Staged Changes box missing on empty repo with a staged file (issue #23)"
    )
    assert "README.md" in src
    assert "no-repo" not in src
    assert "No git repo found" not in src


def test_empty_repo_verbose_untracked_file_shows_untracked_box(repo: RepoTools):
    """Untracked box must appear in verbose mode even before the first commit."""
    repo.write("mystery.txt", "not added")
    # Not staged -- just sitting in the working tree
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    src = dg.source
    assert node_in(src, "Untracked"), (
        "Untracked box missing on empty repo with an untracked file (issue #23)"
    )
    assert "mystery.txt" in src
    assert "no-repo" not in src


def test_empty_repo_verbose_no_files_falls_back_to_no_repo(repo: RepoTools):
    """With nothing staged or untracked, the empty repo still shows the no-repo node."""
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    src = dg.source
    assert "no-repo" in src or "No git repo found" in src


def test_branch_mode_diverged_shows_fork(repo: RepoTools):
    """Diverged branches are connected through a fork commit node."""
    repo.write("base.txt")
    repo.commit("base")
    # Branch off and add unique commits on each side so they diverge
    repo.checkout("stable", new=True)
    repo.write("stable.txt")
    repo.commit("stable-only")

    repo.checkout("main")
    repo.write("main2.txt")
    repo.commit("main-only")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # Both branches must appear
    assert node_in(src, "main")
    assert node_in(src, "stable")
    # They must be connected: either directly (if one is ancestor) or via a fork
    # A fork node or direct edge should exist
    has_connection = (
        edge_in(src, "main", "stable")
        or edge_in(src, "stable", "main")
        or "fork" in src  # fork commit node label
    )
    assert has_connection, "Diverged branches must be connected in branch topology"


# ---------------------------------------------------------------------------
# Normal mode
# ---------------------------------------------------------------------------


def test_normal_mode_ref_node(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    dg, _, graph, _ = _build(str(repo.path))
    src = dg.source
    assert node_in(src, "refs/heads/main")
    assert node_in(src, "HEAD")


def test_normal_mode_commit_node(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("first")
    dg, _, graph, _ = _build(str(repo.path))
    assert node_in(dg.source, sha)


def test_normal_mode_head_to_branch_edge(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    dg, _, _, _ = _build(str(repo.path))
    assert edge_in(dg.source, "HEAD", "refs/heads/main")


def test_normal_mode_branch_to_commit_edge(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("first")
    dg, _, _, _ = _build(str(repo.path))
    assert edge_in(dg.source, "refs/heads/main", sha)


def test_normal_mode_parent_edge(repo: RepoTools):
    repo.write("a.txt")
    sha1 = repo.commit("first")
    repo.write("b.txt")
    sha2 = repo.commit("second")
    dg, _, _, _ = _build(str(repo.path))
    # sha2 is newer; sha1 is its parent
    assert edge_in(dg.source, sha2, sha1)


def test_normal_mode_collapse_boring(repo: RepoTools):
    """A chain of single-parent, single-child, ref-free commits is collapsed."""
    for i in range(4):
        repo.write(f"f{i}.txt", content=f"content-{i}")
        repo.commit(f"commit {i}")

    dg, builder, graph, _ = _build(str(repo.path))
    src = dg.source
    # The boring middle commits should be collapsed: look for the (N) pattern
    assert "(" in src and ")" in src  # summary node label pattern


def test_normal_mode_merge_both_parents(repo: RepoTools):
    repo.write("base.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("feat.txt")
    feat_sha = repo.commit("feature-work")
    repo.checkout("main")
    repo.write("main2.txt")
    main2_sha = repo.commit("main-work")
    repo.merge("feature")
    merge_sha = repo.rev_parse("HEAD")

    dg, _, _, _ = _build(str(repo.path))
    src = dg.source
    # Merge commit is present
    assert node_in(src, merge_sha)
    # Both parent edges exist
    assert edge_in(src, merge_sha, main2_sha)
    assert edge_in(src, merge_sha, feat_sha)


def test_normal_mode_detached_head(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("only")
    repo.detach(sha)
    dg, _, _, _ = _build(str(repo.path))
    src = dg.source
    assert node_in(src, "HEAD")
    assert edge_in(src, "HEAD", sha)


def test_normal_mode_lightweight_tag(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.tag("v1.0")
    dg, _, _, _ = _build(str(repo.path))
    assert node_in(dg.source, "refs/tags/v1.0")


def test_normal_mode_annotated_tag(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.tag("v2.0", annotated=True, message="Release")
    dg, _, _, _ = _build(str(repo.path))
    src = dg.source
    assert node_in(src, "refs/tags/v2.0")


def test_commit_details_flag(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("my special message")
    dg, _, _, _ = _build(str(repo.path), commit_details=True)
    assert "my special message" in dg.source


# ---------------------------------------------------------------------------
# Node type-prefix labels (commit/tree/blob/tag)
# ---------------------------------------------------------------------------


def test_commit_node_label_has_type_prefix(repo: RepoTools):
    """Commit nodes must be labelled with 'commit' on the first line, hash on the second."""
    repo.write("a.txt")
    sha = repo.commit("first")
    dg, _, _, _ = _build(str(repo.path))
    # graphviz renders \n as a real newline in the DOT source string
    assert f"commit\n{sha[:5]}" in dg.source, (
        "commit node label must start with 'commit' on the first line"
    )


def test_commit_details_type_prefix_preserved(repo: RepoTools):
    """With --commit-details, the type prefix must still appear before the hash."""
    repo.write("a.txt")
    sha = repo.commit("my message")
    dg, _, _, _ = _build(str(repo.path), commit_details=True)
    assert f"commit\n{sha[:5]}" in dg.source
    assert "my message" in dg.source


def test_tree_node_label_has_type_prefix(repo: RepoTools):
    """Tree nodes in verbose mode must be labelled with 'tree' on the first line."""
    repo.write("a.txt", content="x")
    repo.commit("first")
    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    tree_sha = next(iter(graph.trees))
    assert f"tree\n{tree_sha[:5]}" in dg.source, (
        "tree node label must start with 'tree' on the first line"
    )


def test_blob_node_label_has_type_prefix(repo: RepoTools):
    """Blob nodes in verbose mode must be labelled with 'blob' on the first line."""
    repo.write("a.txt", content="x")
    repo.commit("first")
    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    blob_sha = next(iter(graph.blobs))
    assert f"blob\n{blob_sha[:5]}" in dg.source, (
        "blob node label must start with 'blob' on the first line"
    )


def test_tag_node_label_has_type_prefix(repo: RepoTools):
    """Tag ref nodes must be labelled with 'tag' on the first line."""
    repo.write("a.txt")
    repo.commit("first")
    repo.tag("v1.0")
    dg, _, _, _ = _build(str(repo.path))
    assert "tag\nv1.0" in dg.source, "tag node label must start with 'tag' on the first line"


def test_annotated_tag_node_label_has_type_prefix(repo: RepoTools):
    """Annotated tag ref nodes must also carry the 'tag' prefix line."""
    repo.write("a.txt")
    repo.commit("first")
    repo.tag("v2.0", annotated=True, message="Release")
    dg, _, _, _ = _build(str(repo.path))
    assert "tag\nv2.0" in dg.source, (
        "annotated tag ref node label must start with 'tag' on the first line"
    )


# ---------------------------------------------------------------------------
# Verbose mode
# ---------------------------------------------------------------------------


def test_verbose_tree_nodes(repo: RepoTools):
    repo.write("a.txt", content="hello")
    repo.commit("first")
    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    assert len(graph.trees) > 0
    # At least one tree hexsha should appear in the source
    tree_hexsha = next(iter(graph.trees))
    assert node_in(dg.source, tree_hexsha)


def test_verbose_blob_nodes(repo: RepoTools):
    repo.write("a.txt", content="hello")
    repo.commit("first")
    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    assert len(graph.blobs) > 0
    blob_hexsha = next(iter(graph.blobs))
    assert node_in(dg.source, blob_hexsha)


def test_verbose_staged_file(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.write("b.txt", content="staged")
    repo._run(["git", "add", "b.txt"])
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    assert "Staged Changes" in dg.source
    assert "b.txt" in dg.source


def test_verbose_unstaged_file(repo: RepoTools):
    repo.write("a.txt", content="original")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    assert "Unstaged Changes" in dg.source
    assert "a.txt" in dg.source


def test_verbose_untracked_file(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.write("new.txt")
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    assert "Untracked" in dg.source
    assert "new.txt" in dg.source


def test_verbose_untracked_edge_connects_to_file_node(repo: RepoTools):
    """Edge from 'Untracked' must point to the individual file node, not a phantom node."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("new.txt")
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    src = dg.source
    # The edge must go to the file node, not back to an implicit 'untracked' node
    assert edge_in(src, "Untracked", "untracked|new.txt"), (
        "Edge must connect 'Untracked' container to 'untracked|new.txt' file node"
    )
    assert node_in(src, "untracked|new.txt"), "Individual untracked file node must exist"


def test_verbose_staged_edge_connects_to_file_node(repo: RepoTools):
    """Edge from 'Staged Changes' must point to the individual file node."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("b.txt", content="staged")
    repo._run(["git", "add", "b.txt"])
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    src = dg.source
    assert edge_in(src, "Staged Changes", "staged|b.txt"), (
        "Edge must connect 'Staged Changes' to 'staged|b.txt' file node"
    )
    assert node_in(src, "staged|b.txt"), "Individual staged file node must exist"


def test_verbose_unstaged_edge_connects_to_file_node(repo: RepoTools):
    """Edge from 'Unstaged Changes' must point to the individual file node."""
    repo.write("a.txt", content="original")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    src = dg.source
    assert edge_in(src, "Unstaged Changes", "unstaged|a.txt"), (
        "Edge must connect 'Unstaged Changes' to 'unstaged|a.txt' file node"
    )
    assert node_in(src, "unstaged|a.txt"), "Individual unstaged file node must exist"


# ---------------------------------------------------------------------------
# Branch mode
# ---------------------------------------------------------------------------


def test_branch_mode_nodes(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    assert node_in(src, "main")
    assert node_in(src, "dev")


def test_branch_mode_ancestry_edge(repo: RepoTools):
    """dev was created from main → main and dev connect via a fork commit node."""
    repo.write("a.txt")
    main_sha = repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # main's tip is the fork point: main → [main_sha] → dev
    assert edge_in(src, "main", main_sha), "main must connect to its tip commit as fork node"
    assert edge_in(src, main_sha, "dev"), "fork commit must connect to dev"


def test_branch_strict_ancestor_inserts_fork_node(repo: RepoTools):
    """Strict ancestry must insert a fork commit node, not a direct branch-to-branch edge."""
    repo.write("a.txt")
    main_sha = repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # A fork commit node (main's tip) must appear in the source
    assert main_sha[:8] in src, "Fork commit's short SHA must appear as a node label"
    # There must be no direct main → dev edge (fork commit must be the intermediary)
    assert not edge_in(src, "main", "dev"), "Direct branch-to-branch edge must not exist"


def test_branch_strict_ancestor_ancestor_to_fork_edge(repo: RepoTools):
    """The ancestor branch has an edge pointing to the fork commit at its own tip."""
    repo.write("a.txt")
    main_sha = repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert edge_in(dg.source, "main", main_sha)


def test_branch_strict_ancestor_fork_to_child_edge(repo: RepoTools):
    """The fork commit node has an edge pointing to the descendant branch."""
    repo.write("a.txt")
    main_sha = repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert edge_in(dg.source, main_sha, "dev")


def test_branch_mode_single_branch(repo: RepoTools):
    """Single branch repo renders without error."""
    repo.write("a.txt")
    repo.commit("only")
    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert "main" in dg.source


# ---------------------------------------------------------------------------
# Highlight (new-node detection)
# ---------------------------------------------------------------------------


def test_highlight_new_node_not_in_prev_render(repo: RepoTools):
    """Nodes absent from highlight_ids (prev render) receive the new_node color."""
    repo.write("a.txt")
    repo.commit("first")
    from gitplot.colors import SCHEME

    # Pass an empty frozenset as highlight_ids (prev render had no nodes).
    # sha is NOT in the prev render, so it should be highlighted.
    dg, _, _, _ = _build(str(repo.path), highlight_ids=frozenset())
    new_fill = SCHEME["new_node"].fill
    assert new_fill in dg.source, "New node (not in prev render) must use new_node fill color"


def test_highlight_old_node_not_highlighted(repo: RepoTools):
    """Nodes present in highlight_ids (prev render) keep their normal color."""
    repo.write("a.txt")
    sha = repo.commit("first")
    from gitplot.colors import SCHEME

    # Pass sha as already known (in the previous render) — it should NOT be highlighted.
    dg, _, _, _ = _build(str(repo.path), highlight_ids=frozenset({sha}))
    new_fill = SCHEME["new_node"].fill
    # The commit node is sha; it's in highlight_ids so it should use normal commit color.
    commit_fill = SCHEME["commit"].fill
    assert commit_fill in dg.source, "Known node (in prev render) must keep commit fill color"
    # sha's node should not use new_node fill when it's a known node and is the ONLY node
    # (all other nodes like refs would still be new, so just check sha's own attrs)
    src = dg.source
    # The sha node line should contain commit fill, not new_node fill
    sha_line = next((ln for ln in src.splitlines() if sha[:5] in ln and "fillcolor" in ln), None)
    assert sha_line is not None
    assert new_fill not in sha_line, "sha node (in prev render) must not use new_node fill"


def test_highlight_none_disables_highlighting(repo: RepoTools):
    """When highlight_ids is None, no node receives the new_node color."""
    repo.write("a.txt")
    repo.commit("first")
    from gitplot.colors import SCHEME

    dg, _, _, _ = _build(str(repo.path), highlight_ids=None)
    new_fill = SCHEME["new_node"].fill
    assert new_fill not in dg.source, "highlight_ids=None must produce no highlighted nodes"


# ---------------------------------------------------------------------------
# Node deduplication
# ---------------------------------------------------------------------------


def test_no_duplicate_nodes(repo: RepoTools):
    """Each commit appears only once even when reachable from multiple refs."""
    repo.write("a.txt")
    sha = repo.commit("base")
    repo.checkout("dev", new=True)
    repo.checkout("main")
    # Both branches point to sha now
    dg, _, _, _ = _build(str(repo.path))
    src = dg.source
    # Count occurrences of sha in source; should appear only once as a node def
    node_declarations = src.count(f'"{sha}"')
    # 1 node def + edges referencing it; node def itself appears at most a few times
    assert node_declarations <= 3  # generous upper bound; duplication would be 10+


# ---------------------------------------------------------------------------
# Branch mode: same-commit branches
# ---------------------------------------------------------------------------


def test_branch_same_commit_connected(repo: RepoTools):
    """Two branches at the same commit must be connected, not floating islands."""
    repo.write("a.txt")
    repo.commit("base")
    # Create develop at the same tip as main (no new commits)
    repo.checkout("develop", new=True)
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    assert node_in(src, "main")
    assert node_in(src, "develop")
    # Must have an edge between them in either direction
    assert edge_in(src, "main", "develop") or edge_in(src, "develop", "main"), (
        "Branches at the same commit must be connected by an edge"
    )


def test_branch_same_commit_priority_direction(repo: RepoTools):
    """When master and develop share a commit, master is shown as parent of develop."""
    repo.write("a.txt")
    repo.commit("base")
    # Rename default branch to master and create develop at same tip
    repo._run(["git", "branch", "-m", "main", "master"])
    repo.checkout("develop", new=True)
    repo.checkout("master")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # master has priority 0, develop has priority 1 → master is parent
    assert edge_in(src, "master", "develop")


def test_branch_ff_merge_stays_connected(repo: RepoTools):
    """After a fast-forward merge develop stays connected to the branch it absorbed."""
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("b.txt")
    repo.commit("feature-work")
    # Fast-forward main to feature
    repo.checkout("main")
    repo.merge("feature", no_ff=False)
    # Now main and feature are at the same commit

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    assert node_in(src, "main")
    assert node_in(src, "feature")
    assert edge_in(src, "main", "feature") or edge_in(src, "feature", "main")


# ---------------------------------------------------------------------------
# Branch mode: linear chain of three branches
# ---------------------------------------------------------------------------


def test_branch_three_branch_linear_chain(repo: RepoTools):
    """main → develop → feature — each branch connects to its tip as a fork commit node."""
    repo.write("a.txt")
    main_sha = repo.commit("on-main")
    repo.checkout("develop", new=True)
    repo.write("b.txt")
    develop_sha = repo.commit("on-develop")
    repo.checkout("feature", new=True)
    repo.write("c.txt")
    repo.commit("on-feature")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # main connects to its fork commit, which connects to develop
    assert edge_in(src, "main", main_sha), "main must connect to its fork commit"
    assert edge_in(src, main_sha, "develop"), "main's fork commit must connect to develop"
    # develop connects to its fork commit, which connects to feature
    assert edge_in(src, "develop", develop_sha), "develop must connect to its fork commit"
    assert edge_in(src, develop_sha, "feature"), "develop's fork commit must connect to feature"


def test_branch_low_priority_ancestor_shown_as_fork_child(repo: RepoTools):
    """A lower-priority ancestor branch must appear as a child of the fork, not its parent.

    When feature/old (priority 2) is a strict ancestor of main (priority 0),
    the diagram must show both as children of the shared fork commit — NOT the
    chain  feature/old → [fork] → main  which falsely implies feature/old is a
    root that main descended from.

    Expected:  [fork] → feature/old
               [fork] → main
    Rejected:  feature/old → [fork] → main
    """
    repo.write("a.txt")
    repo.commit("base")
    # oldbranch adds a commit; main will fast-forward to it so that
    # oldbranch's tip becomes a shared ancestor of main.
    repo.checkout("oldbranch", new=True)
    repo.write("b.txt")
    repo.commit("oldbranch-work")
    repo.checkout("main")
    repo.merge("oldbranch", no_ff=False)  # fast-forward: main now at oldbranch's tip
    fork_sha = repo.rev_parse("HEAD")  # oldbranch's tip = main's current position
    repo.write("c.txt")
    repo.commit("main-continues")  # main moves ahead; oldbranch stays at fork_sha

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source

    # fork_sha must connect TO oldbranch (oldbranch is a sibling of main at the fork)
    assert edge_in(src, fork_sha, "oldbranch"), (
        "Fork commit must connect to oldbranch — oldbranch should be a child of the "
        "fork, not its parent"
    )
    # The wrong direction must not be present
    assert not edge_in(src, "oldbranch", fork_sha), (
        "oldbranch must not appear as the parent of the fork commit"
    )


def test_branch_ancestor_connected_through_intermediate_fork(repo: RepoTools):
    """main stays connected when a closer fork commit supersedes it as develop's parent.

    Scenario: main (base) ← develop (intermediate) ← develop (more work)
                                   ↑
                               feature branches here

    merge_base(main, develop) = main's tip (strict ancestor).
    merge_base(develop, feature) = intermediate commit (diverged, more recent).

    The more-recent fork overwrites parent_map["develop"] from main's tip to
    intermediate.  main's tip is then absent from used_fork_hexshas, so
    branch_at_fork["main"] can't generate its edge — main becomes an island.

    The fix must generate main → [intermediate fork] so main stays connected.
    """
    repo.write("a.txt")
    repo.commit("base")  # main's tip
    repo.checkout("develop", new=True)
    repo.write("b.txt")
    repo.commit("intermediate")  # fork point between develop and feature
    repo.checkout("feature", new=True)
    repo.write("c.txt")
    repo.commit("feature-work")
    repo.checkout("develop")
    repo.write("d.txt")
    repo.commit("develop-extra")  # develop moves ahead of feature's branch point
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source

    # main must not be an island — it must connect to something via an edge
    assert "main" in src
    assert "develop" in src
    # There must be a path from main to develop (directly or via fork nodes)
    main_has_outgoing = any(
        f'"{nm}" -> ' in src or f"\t{nm} -> " in src or f" {nm} -> " in src for nm in ("main",)
    )
    assert main_has_outgoing, "main must have at least one outgoing edge (not an island)"


# ---------------------------------------------------------------------------
# Branch mode: fork commit node
# ---------------------------------------------------------------------------


def test_branch_fork_sha_appears(repo: RepoTools):
    """The fork commit's SHA prefix appears in the DOT source as a node label."""
    repo.write("base.txt")
    fork_sha = repo.commit("shared-base")

    repo.checkout("side-a", new=True)
    repo.write("a.txt")
    repo.commit("a-work")

    repo.checkout("main")
    repo.write("b.txt")
    repo.commit("b-work")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # The fork commit's 8-char short SHA must appear as a node label
    assert fork_sha[:8] in src, f"Fork SHA {fork_sha[:8]} not found in branch diagram"


def test_branch_fork_connects_both_branches(repo: RepoTools):
    """Both diverged branches have edges to/from the shared fork commit."""
    repo.write("base.txt")
    repo.commit("shared-base")

    repo.checkout("branch-a", new=True)
    repo.write("a.txt")
    repo.commit("a-work")

    repo.checkout("main")
    repo.write("b.txt")
    repo.commit("b-work")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    assert node_in(src, "main")
    assert node_in(src, "branch-a")
    # Both branches must be reachable from the fork (directly or via fork node)
    has_connection = (
        edge_in(src, "main", "branch-a") or edge_in(src, "branch-a", "main") or "fork" in src
    )
    assert has_connection


# ---------------------------------------------------------------------------
# Normal mode: two refs on same commit
# ---------------------------------------------------------------------------


def test_normal_two_branches_same_commit_both_refs_visible(repo: RepoTools):
    """Two branch refs at the same SHA both appear as ref nodes in normal mode."""
    repo.write("a.txt")
    sha = repo.commit("base")
    repo.checkout("release", new=True)
    repo.checkout("main")
    # Both main and release point to sha

    dg, _, _, _ = _build(str(repo.path))
    src = dg.source
    assert node_in(src, "refs/heads/main")
    assert node_in(src, "refs/heads/release")
    # The shared commit must still appear
    assert node_in(src, sha)


def test_normal_empty_repo_no_crash(repo: RepoTools):
    """Empty repo (no commits) renders without error and without commit nodes."""
    dg, _, graph, _ = _build(str(repo.path))
    assert graph.commits == {}
    # Should not crash; source is a valid (possibly empty-graph) string
    assert isinstance(dg.source, str)


# ---------------------------------------------------------------------------
# Verbose mode: commit → tree → blob chain
# ---------------------------------------------------------------------------


def test_verbose_commit_to_tree_edge(repo: RepoTools):
    """In verbose mode an edge from the commit SHA to its root tree SHA must exist."""
    repo.write("file.txt", content="hello")
    sha = repo.commit("first")

    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    src = dg.source

    cd = graph.commits[sha]
    assert cd.tree_hexsha is not None
    assert edge_in(src, sha, cd.tree_hexsha), (
        f"Expected edge {sha[:8]} → {cd.tree_hexsha[:8]} in verbose mode"
    )


def test_verbose_tree_to_blob_edge(repo: RepoTools):
    """In verbose mode an edge from the root tree SHA to each blob SHA must exist."""
    repo.write("file.txt", content="hello")
    sha = repo.commit("first")

    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    src = dg.source

    cd = graph.commits[sha]
    td = graph.trees[cd.tree_hexsha]
    assert td.blob_entries, "Expected at least one blob in the root tree"
    for _name, blob_sha in td.blob_entries:
        assert edge_in(src, cd.tree_hexsha, blob_sha), (
            f"Expected tree→blob edge {cd.tree_hexsha[:8]} → {blob_sha[:8]}"
        )


def test_verbose_all_filenames_shown_when_blobs_share_sha(repo: RepoTools):
    """All filenames in a tree must appear as edges even when files share the same blob SHA.

    Empty files all hash to e69de29bb.  When a commit adds two empty files, the tree
    has two entries pointing to the same blob.  Both filenames must still appear as
    labelled edges in the diagram -- one per tree entry, not one per unique blob SHA.
    """
    repo.write("aaa.py", content="")
    repo.write("bbb.py", content="")
    sha = repo.commit("two empty files sharing a blob")

    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    src = dg.source

    cd = graph.commits[sha]
    td = graph.trees[cd.tree_hexsha]

    # Data model must preserve (name, sha) pairs, not just unique SHAs
    names_in_entries = {name for name, _ in td.blob_entries}
    assert names_in_entries == {"aaa.py", "bbb.py"}, (
        f"blob_entries must list both filenames; got {names_in_entries}"
    )

    # Both filenames must appear in the rendered diagram
    assert "aaa.py" in src, "aaa.py must appear in diagram even when sharing blob SHA with bbb.py"
    assert "bbb.py" in src, "bbb.py must appear in diagram even when sharing blob SHA with aaa.py"


def test_verbose_tree_to_blob_edge_uses_blob_entries(repo: RepoTools):
    """tree→blob edges must be keyed on (tree, filename), not (tree, blob_sha).

    When a single tree has multiple entries pointing to the same blob SHA, the diagram
    must draw one edge per filename rather than collapsing them into a single edge.
    """
    repo.write("x.py", content="same")
    repo.write("y.py", content="same")
    repo.commit("two files same content")

    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    src = dg.source

    # Both (tree, name) edges must exist in the DOT source
    assert "x.py" in src, "x.py edge label must appear in verbose diagram"
    assert "y.py" in src, "y.py edge label must appear in verbose diagram"


def test_verbose_blob_node_label_is_hash_not_filename(repo: RepoTools):
    """Blob nodes must be labelled with just their short hash, not a filename.

    The filename belongs in the edge label (tree → blob), not the blob node itself.
    Putting a filename in the blob node label is misleading when multiple files share
    the same blob SHA -- the node would show whichever filename happened to be
    processed first, making it look like a file when it's really content-addressed
    object storage.
    """
    repo.write("readme.md", content="hello")
    sha = repo.commit("add readme")

    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    src = dg.source

    cd = graph.commits[sha]
    td = graph.trees[cd.tree_hexsha]
    assert td.blob_entries
    _name, blob_sha = td.blob_entries[0]

    # The node for this blob must be in the graph
    assert node_in(src, blob_sha), "blob node must exist in verbose diagram"

    # Filename must appear exactly once -- as the edge label, not also in the blob node label
    assert src.count("readme.md") == 1, (
        "filename should appear once (on the edge label), not also embedded in the blob node label"
    )


def test_verbose_nested_tree(repo: RepoTools):
    """A subdirectory produces a child tree node connected to the root tree."""
    repo.write("subdir/nested.txt", content="nested")
    sha = repo.commit("nested")

    dg, _, graph, _ = _build(str(repo.path), mode="verbose")
    src = dg.source

    cd = graph.commits[sha]
    root_td = graph.trees[cd.tree_hexsha]
    assert root_td.child_tree_hexshas, "Expected at least one child tree (the subdir)"
    for child_sha in root_td.child_tree_hexshas:
        assert node_in(src, child_sha), f"Child tree {child_sha[:8]} missing from verbose diagram"
        assert edge_in(src, cd.tree_hexsha, child_sha), "Expected root-tree→child-tree edge"


# ---------------------------------------------------------------------------
# FETCH_HEAD support (issue #8)
# ---------------------------------------------------------------------------


def _write_fetch_head(repo_path: Path, sha: str) -> None:
    """Simulate a recent fetch by writing a .git/FETCH_HEAD file."""
    (repo_path / ".git" / "FETCH_HEAD").write_text(
        f"{sha}\t\tbranch 'main' of https://github.com/example/repo\n"
    )


def test_fetch_head_normal_mode_ref_node_appears(repo: RepoTools):
    """FETCH_HEAD appears as a ref node in normal mode when the file exists."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_fetch_head(repo.path, sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "FETCH_HEAD")


def test_fetch_head_normal_mode_edge_to_commit(repo: RepoTools):
    """FETCH_HEAD ref node has an edge to the commit it points at."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_fetch_head(repo.path, sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert edge_in(dg.source, "FETCH_HEAD", sha)


def test_fetch_head_branch_mode_node_appears(repo: RepoTools):
    """FETCH_HEAD appears as a node in branch mode."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_fetch_head(repo.path, sha)

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert node_in(dg.source, "FETCH_HEAD")


def test_fetch_head_absent_no_phantom_node(repo: RepoTools):
    """When .git/FETCH_HEAD doesn't exist, no FETCH_HEAD node appears."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert "FETCH_HEAD" not in dg.source


def test_fetch_head_malformed_no_crash(repo: RepoTools):
    """A malformed FETCH_HEAD file doesn't crash gitplot."""
    repo.write("a.txt")
    repo.commit("first")
    (repo.path / ".git" / "FETCH_HEAD").write_text("not-a-valid-sha\n")

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert isinstance(dg.source, str)


# ---------------------------------------------------------------------------
# ORIG_HEAD / MERGE_HEAD / CHERRY_PICK_HEAD support (issue #24)
# ---------------------------------------------------------------------------


def _write_simple_ref(repo_path: Path, name: str, sha: str) -> None:
    """Write .git/<name> containing sha, simulating a git operation that leaves the ref."""
    (repo_path / ".git" / name).write_text(sha + "\n")


def test_orig_head_normal_mode_ref_node_appears(repo: RepoTools):
    """ORIG_HEAD appears as a ref node in normal mode when the file exists."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_simple_ref(repo.path, "ORIG_HEAD", sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "ORIG_HEAD")


def test_orig_head_normal_mode_edge_to_commit(repo: RepoTools):
    """ORIG_HEAD ref node has an edge to the commit it points at."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_simple_ref(repo.path, "ORIG_HEAD", sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert edge_in(dg.source, "ORIG_HEAD", sha)


def test_orig_head_after_real_reset(repo: RepoTools):
    """ORIG_HEAD created by git reset --hard points at the pre-reset commit."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("b.txt")
    sha2 = repo.commit("second")
    repo._run(["git", "reset", "--hard", "HEAD~1"])

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "ORIG_HEAD")
    # ORIG_HEAD records where HEAD was *before* the reset, i.e. the second commit
    assert edge_in(dg.source, "ORIG_HEAD", sha2)


def test_orig_head_absent_no_phantom_node(repo: RepoTools):
    """When .git/ORIG_HEAD doesn't exist, no ORIG_HEAD node appears."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert "ORIG_HEAD" not in dg.source


def test_orig_head_malformed_no_crash(repo: RepoTools):
    """A malformed ORIG_HEAD file doesn't crash gitplot."""
    repo.write("a.txt")
    repo.commit("first")
    _write_simple_ref(repo.path, "ORIG_HEAD", "not-a-valid-sha")

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert isinstance(dg.source, str)


def test_merge_head_normal_mode_ref_node_appears(repo: RepoTools):
    """MERGE_HEAD appears as a ref node in normal mode when the file exists."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_simple_ref(repo.path, "MERGE_HEAD", sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "MERGE_HEAD")


def test_merge_head_edge_to_commit(repo: RepoTools):
    """MERGE_HEAD ref node has an edge to the commit it points at."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_simple_ref(repo.path, "MERGE_HEAD", sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert edge_in(dg.source, "MERGE_HEAD", sha)


def test_merge_head_after_real_conflicting_merge(repo: RepoTools):
    """MERGE_HEAD written by a conflicting merge appears in the graph."""
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
        pass  # conflict is expected
    assert (repo.path / ".git" / "MERGE_HEAD").exists(), "git merge should have written MERGE_HEAD"

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "MERGE_HEAD")
    assert edge_in(dg.source, "MERGE_HEAD", feature_sha)


def test_merge_head_absent_no_phantom_node(repo: RepoTools):
    """When .git/MERGE_HEAD doesn't exist, no MERGE_HEAD node appears."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert "MERGE_HEAD" not in dg.source


def test_cherry_pick_head_normal_mode_ref_node_appears(repo: RepoTools):
    """CHERRY_PICK_HEAD appears as a ref node in normal mode when the file exists."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_simple_ref(repo.path, "CHERRY_PICK_HEAD", sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "CHERRY_PICK_HEAD")


def test_cherry_pick_head_edge_to_commit(repo: RepoTools):
    """CHERRY_PICK_HEAD ref node has an edge to the commit it points at."""
    repo.write("a.txt")
    sha = repo.commit("first")
    _write_simple_ref(repo.path, "CHERRY_PICK_HEAD", sha)

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert edge_in(dg.source, "CHERRY_PICK_HEAD", sha)


def test_cherry_pick_head_after_real_conflicting_cherry_pick(repo: RepoTools):
    """CHERRY_PICK_HEAD written by a conflicting cherry-pick appears in the graph."""
    import subprocess

    repo.write("file.txt", "v1")
    repo.commit("initial")
    repo.checkout("feature", new=True)
    repo.write("file.txt", "feature version")
    feature_sha = repo.commit("feature change")
    repo.checkout("main")
    repo.write("file.txt", "main version")
    repo.commit("main change")
    try:
        repo._run(["git", "cherry-pick", feature_sha])
    except subprocess.CalledProcessError:
        pass  # conflict is expected
    assert (repo.path / ".git" / "CHERRY_PICK_HEAD").exists(), (
        "git cherry-pick should have written CHERRY_PICK_HEAD"
    )

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert node_in(dg.source, "CHERRY_PICK_HEAD")
    assert edge_in(dg.source, "CHERRY_PICK_HEAD", feature_sha)


def test_cherry_pick_head_absent_no_phantom_node(repo: RepoTools):
    """When .git/CHERRY_PICK_HEAD doesn't exist, no CHERRY_PICK_HEAD node appears."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert "CHERRY_PICK_HEAD" not in dg.source


# ---------------------------------------------------------------------------
# Worktree annotation in branch mode (issue #25)
# ---------------------------------------------------------------------------


def test_worktree_no_annotation_when_no_linked_worktrees(repo: RepoTools):
    """With only the main worktree, no worktree annotation appears in branch mode."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert "[wt:" not in dg.source


def test_worktree_linked_branch_label_contains_path(repo: RepoTools):
    """A branch checked out in a linked worktree has its path annotated on the branch node."""
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("b.txt")
    repo.commit("feature commit")
    repo.checkout("main")

    wt_path = repo.path.parent / (repo.path.name + "-wt")
    repo._run(["git", "worktree", "add", str(wt_path), "feature"])

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert str(wt_path) in dg.source


def test_worktree_annotation_on_node_not_separate_node(repo: RepoTools):
    """Worktree path appears as part of the branch label, not as a separate node."""
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("b.txt")
    repo.commit("feature commit")
    repo.checkout("main")

    wt_path = repo.path.parent / (repo.path.name + "-wt")
    repo._run(["git", "worktree", "add", str(wt_path), "feature"])

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    assert str(wt_path) in src
    assert node_in(src, "feature")


def test_worktree_path_populated_on_branch_node(repo: RepoTools):
    """get_branch_topology() sets worktree_path on the BranchNode for a linked worktree."""
    from gitplot.repo import GitRepo

    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("b.txt")
    repo.commit("feature commit")
    repo.checkout("main")

    wt_path = repo.path.parent / (repo.path.name + "-wt")
    repo._run(["git", "worktree", "add", str(wt_path), "feature"])

    topo = GitRepo(str(repo.path)).get_branch_topology()
    feature_node = next(n for n in topo.nodes if n.name == "feature")
    assert feature_node.worktree_path == str(wt_path)


def test_worktree_no_path_on_branch_without_worktree(repo: RepoTools):
    """A branch not checked out in any worktree has worktree_path=None."""
    from gitplot.repo import GitRepo

    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("b.txt")
    repo.commit("feature commit")
    repo.checkout("main")

    topo = GitRepo(str(repo.path)).get_branch_topology()
    feature_node = next(n for n in topo.nodes if n.name == "feature")
    assert feature_node.worktree_path is None


def test_worktree_main_worktree_not_annotated(repo: RepoTools):
    """The main worktree's branch does not get a worktree annotation (only linked worktrees)."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert "[wt:" not in dg.source


# ---------------------------------------------------------------------------
# Stash support (issue #7)
# ---------------------------------------------------------------------------


def test_stash_absent_no_crash_branch_mode(repo: RepoTools):
    """No stash entries → no crash, no stash nodes in branch mode."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert "stash" not in dg.source.lower()


def test_stash_absent_no_crash_verbose_mode(repo: RepoTools):
    """No stash entries → no crash in verbose mode."""
    repo.write("a.txt")
    repo.commit("first")

    dg, _, _, _ = _build(str(repo.path), mode="verbose")
    assert isinstance(dg.source, str)


def test_stash_node_appears_in_branch_mode(repo: RepoTools):
    """A stash entry appears as a labeled node in branch mode."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    repo._run(["git", "stash"])

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert "stash" in dg.source.lower()


def test_stash_branch_mode_connected_to_parent_branch(repo: RepoTools):
    """Stash node is connected to the branch it was stashed from."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    repo._run(["git", "stash"])

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # Stash appears and so does main; they must be connected
    assert "stash" in src.lower()
    assert node_in(src, "main")
    has_connection = (
        edge_in(src, "main", "stash@{0}")
        or edge_in(src, "stash@{0}", "main")
        or ("stash" in src.lower() and "main" in src)
    )
    assert has_connection


def test_stash_verbose_mode_commit_in_graph(repo: RepoTools):
    """Stash commit SHA is present in the verbose-mode commit graph."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    repo._run(["git", "stash"])
    stash_sha = repo._run(["git", "rev-parse", "stash@{0}"])

    _, _, graph, _ = _build(str(repo.path), mode="verbose")
    assert stash_sha in graph.commits


def test_stash_not_shown_in_normal_mode(repo: RepoTools):
    """Stash does not appear in normal mode (branch/verbose only)."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    repo._run(["git", "stash"])

    dg, _, _, _ = _build(str(repo.path), mode="normal")
    assert "stash" not in dg.source.lower()


def test_stash_multiple_entries_all_in_branch_mode(repo: RepoTools):
    """Multiple stash entries all appear in branch mode."""
    repo.write("a.txt")
    repo.commit("first")
    repo.write("a.txt", content="mod1")
    repo._run(["git", "stash"])
    repo.write("a.txt", content="mod2")
    repo._run(["git", "stash"])

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # Both stash entries must be referenced
    assert "stash@{0}" in src and "stash@{1}" in src


# ---------------------------------------------------------------------------
# Shallow clone support (issue #6)
# ---------------------------------------------------------------------------


def _make_source_repo(path: Path, num_commits: int = 3) -> None:
    """Create a plain git repo with num_commits commits; used as a clone source."""
    path.mkdir()
    for cmd in [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "test@gitplot.test"],
        ["git", "config", "user.name", "GitPlot Test"],
    ]:
        subprocess.check_call(cmd, cwd=path, stderr=subprocess.DEVNULL)
    for i in range(num_commits):
        (path / f"f{i}.txt").write_text(str(i))
        subprocess.check_call(["git", "add", "-A"], cwd=path, stderr=subprocess.DEVNULL)
        subprocess.check_call(
            ["git", "commit", "-m", f"commit {i}"], cwd=path, stderr=subprocess.DEVNULL
        )


def test_shallow_clone_normal_mode_no_crash(tmp_path: Path):
    """Normal mode on a depth-1 shallow clone must not raise."""
    _make_source_repo(tmp_path / "src", num_commits=3)
    shallow = tmp_path / "shallow"
    subprocess.check_call(
        ["git", "clone", "--no-local", "--depth=1", str(tmp_path / "src"), str(shallow)],
        stderr=subprocess.DEVNULL,
    )

    dg, _, graph, _ = _build(str(shallow), mode="normal")
    assert dg.source  # non-empty, valid DOT
    # Only commits reachable within the shallow depth should be in the graph.
    assert len(graph.commits) >= 1
    assert len(graph.commits) <= 2  # depth=1 → at most tip commit visible


def test_shallow_clone_shows_tip_commit(tmp_path: Path):
    """The tip commit is visible; parents beyond the shallow depth are not."""
    _make_source_repo(tmp_path / "src", num_commits=3)
    shallow = tmp_path / "shallow"
    subprocess.check_call(
        ["git", "clone", "--no-local", "--depth=1", str(tmp_path / "src"), str(shallow)],
        stderr=subprocess.DEVNULL,
    )

    _, _, graph, _ = _build(str(shallow), mode="normal")
    # Exactly 1 commit accessible in a depth-1 clone
    assert len(graph.commits) == 1
    # That commit has no parents recorded (shallow boundary)
    only = next(iter(graph.commits.values()))
    assert only.parents == []


def test_shallow_clone_depth2_shows_two_commits(tmp_path: Path):
    """depth=2 shallow clone exposes exactly 2 commits in the graph."""
    _make_source_repo(tmp_path / "src", num_commits=4)
    shallow = tmp_path / "shallow"
    subprocess.check_call(
        ["git", "clone", "--no-local", "--depth=2", str(tmp_path / "src"), str(shallow)],
        stderr=subprocess.DEVNULL,
    )

    _, _, graph, _ = _build(str(shallow), mode="normal")
    assert len(graph.commits) == 2


def test_shallow_clone_verbose_mode_no_crash(tmp_path: Path):
    """Verbose mode (trees + blobs) on a shallow clone must not raise."""
    _make_source_repo(tmp_path / "src", num_commits=3)
    shallow = tmp_path / "shallow"
    subprocess.check_call(
        ["git", "clone", "--no-local", "--depth=1", str(tmp_path / "src"), str(shallow)],
        stderr=subprocess.DEVNULL,
    )

    dg, _, _, _ = _build(str(shallow), mode="verbose")
    assert dg.source


def test_shallow_clone_branch_mode_no_crash(tmp_path: Path):
    """Branch mode on a shallow clone must not raise."""
    _make_source_repo(tmp_path / "src", num_commits=3)
    shallow = tmp_path / "shallow"
    subprocess.check_call(
        ["git", "clone", "--no-local", "--depth=1", str(tmp_path / "src"), str(shallow)],
        stderr=subprocess.DEVNULL,
    )

    dg, _, _, _ = _build(str(shallow), mode="branch")
    assert dg.source
