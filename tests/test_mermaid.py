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


def test_mermaid_node_unquoted_label():
    """Unquoted DOT label (label=short) must appear as display label, not the full node ID.

    graphviz omits quotes around a label when it's a plain alphanumeric word;
    the label regex must handle this or the full node ID leaks into the output.
    """
    # Node ID = full hash starting with a letter (graphviz leaves it unquoted).
    # Label   = short 5-char hash (also alphanumeric → also unquoted by graphviz).
    dot = (
        "digraph {\n"
        '\ta160d5d8e8db2bcdde95e98515bbe496f4768e60 [label=a160d color="0.1 1.0 1.0"'
        ' fillcolor="0.1 0.1 1.0" penwidth=2 style=filled]\n'
        "}\n"
    )
    out = dot_to_mermaid(dot)
    # Display label must be the short hash, not the 40-char node ID
    assert '["a160d"]' in out
    # Full hash must not appear between [ and ] (i.e. not used as a label)
    assert '["a160d5d8e8db2bcdde95e98515bbe496f4768e60"]' not in out


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


_NODE_COLORED = (
    '\tabc123 [label="abc12" color="0.000 1.000 1.000"'
    ' fillcolor="0.000 0.100 1.000" penwidth=2 style=filled]'
)
_NODE_RED = (
    '\tabc123 [label="abc12" color="0.000 1.000 1.000"'
    ' fillcolor="0.000 1.000 1.000" penwidth=2 style=filled]'
)
_NODE_TINTED = (
    '\tabc123 [label="abc12" color="0.222 1.000 1.000"'
    ' fillcolor="0.222 0.100 1.000" penwidth=2 style=filled]'
)


def test_mermaid_style_line_emitted_for_colored_node():
    """Nodes with fillcolor/color HSV attrs must produce a Mermaid style directive."""
    out = dot_to_mermaid(f"digraph {{\n{_NODE_COLORED}\n}}\n")
    assert "style abc123" in out
    assert "fill:#" in out
    assert "stroke:#" in out


def test_mermaid_hsv_pure_red_to_hex():
    """HSV(0, 1, 1) = pure red = #ff0000 for both fill and stroke."""
    out = dot_to_mermaid(f"digraph {{\n{_NODE_RED}\n}}\n")
    assert "fill:#ff0000" in out
    assert "stroke:#ff0000" in out


def test_mermaid_hsv_fill_lighter_than_stroke():
    """fillcolor (low saturation) produces a lighter hex than color (high saturation)."""
    # color = HSV(0.222, 1.0, 1.0) — vivid; fillcolor = HSV(0.222, 0.1, 1.0) — pale
    out = dot_to_mermaid(f"digraph {{\n{_NODE_TINTED}\n}}\n")
    assert "style abc123 fill:#" in out
    style_line = next(p for p in out.splitlines() if "fill:#" in p)
    fill_hex = style_line.split("fill:#")[1].split(",")[0]
    stroke_hex = style_line.split("stroke:#")[1].split(",")[0].rstrip()
    assert fill_hex != stroke_hex


def test_mermaid_integration_has_style_lines(repo: RepoTools):
    """A real repo built with output_format='mermaid' must have style lines in the output."""
    repo.write("a.txt")
    repo.commit("first")
    graph = GitRepo(str(repo.path)).build_graph()
    builder = GraphBuilder(mode="normal", rank_direction="RL", output_format="mermaid")
    dg = builder.build(graph)
    from gitplot.mermaid import dot_to_mermaid

    out = dot_to_mermaid(dg.source)
    assert "style " in out
    assert "fill:#" in out


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


def test_mermaid_branch_mode_fork_node_is_labeled(repo: RepoTools):
    """Fork commit nodes (multi-line DOT labels) must appear as labeled Mermaid nodes.

    graphviz puts a literal newline inside the label string when the label contains \\n.
    The Mermaid converter must handle this so fork nodes get a proper node declaration
    instead of appearing only as bare hexshas in edge lines.
    """
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    out = _build_mermaid(repo, mode="branch")
    node_def_lines = [ln.strip() for ln in out.splitlines() if '["' in ln and "-->" not in ln]
    assert any("fork" in ln for ln in node_def_lines), (
        "Fork commit nodes must appear as labeled Mermaid nodes (with 'fork' in the label), "
        "not as bare hexshas embedded only in edge lines"
    )


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
