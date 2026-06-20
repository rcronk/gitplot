"""Tests for Mermaid diagram output (issue #9)."""

from __future__ import annotations

from gitplot.builder import GraphBuilder
from gitplot.mermaid import dot_to_mermaid
from gitplot.repo import GitRepo

from .conftest import RepoTools

# ---------------------------------------------------------------------------
# Unit tests for dot_to_mermaid() DOT→Mermaid converter
# ---------------------------------------------------------------------------


def test_mermaid_header_rankdir_rl():
    dot = "digraph {\n\tgraph [rankdir=RL]\n}\n"
    out = dot_to_mermaid(dot)
    assert out.startswith("flowchart RL")


def test_mermaid_header_rankdir_lr():
    dot = "digraph {\n\tgraph [rankdir=LR]\n}\n"
    out = dot_to_mermaid(dot)
    assert out.startswith("flowchart LR")


def test_mermaid_node_with_label():
    dot = (
        "digraph {\n"
        '\tabc123 [label="abc12" color="red" fillcolor="blue" penwidth=2 style=filled]\n'
        "}\n"
    )
    out = dot_to_mermaid(dot)
    assert 'abc123["abc12"]' in out


def test_mermaid_node_quoted_id():
    """Quoted DOT IDs (e.g. refs/heads/main) are handled."""
    dot = (
        "digraph {\n"
        '\t"refs/heads/main" [label="main" color="red" fillcolor="blue" penwidth=2 style=filled]\n'
        "}\n"
    )
    out = dot_to_mermaid(dot)
    # Sanitized ID replaces / with _, label stays "main"
    assert '["main"]' in out
    assert "refs/heads/main" not in out  # raw ID must not appear as-is


def test_mermaid_stash_node_id_sanitized():
    """stash@{0} node ID is sanitized; label is preserved."""
    dot = (
        "digraph {\n"
        '\t"stash@{0}" [label="stash@{0}" color="red" fillcolor="blue" penwidth=2 style=filled]\n'
        "}\n"
    )
    out = dot_to_mermaid(dot)
    # Label is preserved in quotes
    assert '["stash@{0}"]' in out
    # The node ID before [ must not contain @, {, }
    lines = [ln.strip() for ln in out.splitlines() if '["stash@{0}"]' in ln]
    assert lines, "Expected a line with the stash label"
    node_id = lines[0].split("[")[0].strip()
    assert "@" not in node_id and "{" not in node_id and "}" not in node_id


def test_mermaid_edge_no_label():
    dot = "digraph {\n\tabc123 -> def456\n}\n"
    out = dot_to_mermaid(dot)
    assert "abc123 --> def456" in out


def test_mermaid_edge_with_empty_label():
    dot = 'digraph {\n\tabc123 -> def456 [label=""]\n}\n'
    out = dot_to_mermaid(dot)
    # Empty label: plain arrow (no label decoration)
    assert "abc123 --> def456" in out
    assert "|" not in out


def test_mermaid_edge_with_label():
    dot = 'digraph {\n\tabc123 -> def456 [label="parent"]\n}\n'
    out = dot_to_mermaid(dot)
    # Non-empty label: decorated arrow
    assert "abc123" in out and "def456" in out
    assert "parent" in out


def test_mermaid_multiple_nodes_and_edges():
    dot = (
        "digraph {\n"
        "\tgraph [rankdir=RL]\n"
        '\tmain [label="HEAD→main" color="red" fillcolor="blue" penwidth=2 style=filled]\n'
        '\tabc12 [label="abc12" color="grey" fillcolor="grey" penwidth=2 style=filled]\n'
        '\tmain -> abc12 [label="branch"]\n'
        "}\n"
    )
    out = dot_to_mermaid(dot)
    assert "flowchart RL" in out
    assert 'main["HEAD→main"]' in out
    assert 'abc12["abc12"]' in out
    assert "main" in out and "abc12" in out


# ---------------------------------------------------------------------------
# Integration: build a real repo and get Mermaid output
# ---------------------------------------------------------------------------


def _build_mermaid(repo: RepoTools, mode: str = "normal") -> str:
    include_trees = mode == "verbose"
    graph = GitRepo(str(repo.path)).build_graph(include_trees=include_trees)
    if mode == "branch":
        branch_topo = GitRepo(str(repo.path)).get_branch_topology()
    else:
        branch_topo = None
    rank = "LR" if mode == "branch" else "RL"
    builder = GraphBuilder(mode=mode, rank_direction=rank, output_format="svg")
    dg = builder.build(graph, branch_topology=branch_topo)
    return dot_to_mermaid(dg.source)


def test_mermaid_integration_single_commit(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    out = _build_mermaid(repo)
    assert "flowchart" in out
    assert "main" in out.lower()


def test_mermaid_integration_has_edges(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.write("b.txt")
    repo.commit("second")
    out = _build_mermaid(repo)
    assert "-->" in out


def test_mermaid_integration_branch_mode(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("feature", new=True)
    repo.write("b.txt")
    repo.commit("feat")
    repo.checkout("main")
    out = _build_mermaid(repo, mode="branch")
    assert "flowchart LR" in out
    assert "main" in out


def test_builder_accepts_mermaid_output_format(repo: RepoTools):
    """GraphBuilder.build() must not raise when output_format='mermaid'.

    Previously, passing 'mermaid' straight to graphviz.Digraph(format=...) caused
    a ValueError because graphviz doesn't know that format.
    """
    repo.write("a.txt")
    repo.commit("first")
    graph = GitRepo(str(repo.path)).build_graph()
    builder = GraphBuilder(mode="normal", rank_direction="RL", output_format="mermaid")
    dg = builder.build(graph)  # must not raise
    assert dg.source  # sanity: something was produced


def test_mermaid_is_valid_structure(repo: RepoTools):
    """Mermaid output must start with flowchart and contain only safe IDs."""
    repo.write("a.txt")
    repo.commit("first")
    out = _build_mermaid(repo)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines[0].startswith("flowchart")
    # Every node-defining line: id["label"] — id must not contain /, @, {, }
    for line in lines[1:]:
        stripped = line.strip()
        if "[" in stripped and "-->" not in stripped:
            node_id = stripped.split("[")[0].strip()
            for bad_char in ("/", "@", "{", "}"):
                assert bad_char not in node_id, (
                    f"Unsafe char '{bad_char}' in Mermaid node ID: {node_id!r}"
                )
