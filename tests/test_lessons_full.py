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
