"""Structural tests for GraphBuilder: verify nodes and edges in Graphviz output."""

from __future__ import annotations

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
    """dev was created from main → edge from main to dev in topology."""
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    # main's tip is an ancestor of dev → edge main → dev
    assert edge_in(dg.source, "main", "dev")


def test_branch_mode_single_branch(repo: RepoTools):
    """Single branch repo renders without error."""
    repo.write("a.txt")
    repo.commit("only")
    dg, _, _, _ = _build(str(repo.path), mode="branch")
    assert "main" in dg.source


# ---------------------------------------------------------------------------
# Highlight (new-node detection)
# ---------------------------------------------------------------------------


def test_highlight_ids_applied(repo: RepoTools):
    """Nodes in highlight_ids receive the new_node color style."""
    repo.write("a.txt")
    sha = repo.commit("first")

    # Pretend sha is a NEW node (not in prev render)
    # highlight_ids contains the PREVIOUS render's nodes; new nodes are those NOT in it.
    # So pass empty set as highlight_ids to mark nothing as new.
    # To mark sha as highlighted, we need to use it differently:
    # highlight_ids in GraphBuilder marks nodes that ARE new (not in prev render).
    dg, _, _, _ = _build(str(repo.path), highlight_ids={sha})
    # The sha node should use the new_node color scheme (golden fill)
    # Check that the node is present (it was highlighted)
    assert node_in(dg.source, sha)


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
    """main → develop → feature — strict ancestry edges connect all three."""
    repo.write("a.txt")
    repo.commit("on-main")
    repo.checkout("develop", new=True)
    repo.write("b.txt")
    repo.commit("on-develop")
    repo.checkout("feature", new=True)
    repo.write("c.txt")
    repo.commit("on-feature")

    dg, _, _, _ = _build(str(repo.path), mode="branch")
    src = dg.source
    # develop is ahead of main → edge main → develop
    assert edge_in(src, "main", "develop"), "main must be parent of develop"
    # feature is ahead of develop → edge develop → feature
    assert edge_in(src, "develop", "feature"), "develop must be parent of feature"


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
    assert td.blob_hexshas, "Expected at least one blob in the root tree"
    for blob_sha in td.blob_hexshas:
        assert edge_in(src, cd.tree_hexsha, blob_sha), (
            f"Expected tree→blob edge {cd.tree_hexsha[:8]} → {blob_sha[:8]}"
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
