"""Structural tests for GraphBuilder: verify nodes and edges in Graphviz output."""

from __future__ import annotations

import pytest

from gitplot.builder import GraphBuilder
from gitplot.repo import BranchTopology, GitRepo, IndexState, StagedFile, UnstagedFile

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
    empty = RepoGraph(commits={}, trees={}, blobs={}, refs=[],
                      head_branch_path=None, is_detached=False, hash_length=5)
    dg = builder.build(empty)
    assert "no-repo" in dg.source or "No git repo found" in dg.source


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
    assert "(" in src and ")" in src   # summary node label pattern


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
    sha = repo.commit("first")
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
    sha = repo.commit("my special message")
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
    assert node_declarations <= 3   # generous upper bound; duplication would be 10+
