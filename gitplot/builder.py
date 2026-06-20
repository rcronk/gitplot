"""Graph builder: converts RepoGraph data into a graphviz.Digraph.

All Graphviz-specific logic lives here; no GitPython objects enter.
"""

from __future__ import annotations

import logging
from typing import Optional

import graphviz

from .colors import SCHEME, NodeColors
from .repo import (
    BranchTopology,
    CommitData,
    IndexState,
    RepoGraph,
)

log = logging.getLogger(__name__)


class GraphBuilder:
    """Builds a graphviz.Digraph from repo data.

    Instantiate once per render; call build() to produce the Digraph.
    After build(), node_ids contains the IDs of every node added—used by
    Monitor to track what's new between renders.
    """

    def __init__(
        self,
        mode: str,
        rank_direction: str = "RL",
        output_format: str = "svg",
        commit_details: bool = False,
        highlight_ids: Optional[set[str]] = None,
    ) -> None:
        self.mode = mode
        self.rank_direction = rank_direction
        self.output_format = output_format
        self.commit_details = commit_details
        self.highlight_ids: set[str] = highlight_ids or set()

        self._rendered_nodes: set[str] = set()
        self._rendered_edges: set[tuple[str, str]] = set()

    @property
    def node_ids(self) -> frozenset[str]:
        return frozenset(self._rendered_nodes)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(
        self,
        graph: RepoGraph,
        index_state: Optional[IndexState] = None,
        branch_topology: Optional[BranchTopology] = None,
    ) -> graphviz.Digraph:
        dg = graphviz.Digraph(format=self.output_format, engine="dot")
        dg.graph_attr["rankdir"] = self.rank_direction

        if not graph.commits and not branch_topology:
            self._add_node(dg, "no-repo", label="No git repo found", type_key="ref")
            return dg

        if self.mode == "branch":
            self._build_branch(dg, branch_topology or BranchTopology([], [], None, None))
        else:
            self._build_commits(dg, graph)
            if self.mode == "verbose" and index_state:
                self._build_index(dg, graph, index_state)

        return dg

    # ------------------------------------------------------------------
    # Commit modes (normal + verbose)
    # ------------------------------------------------------------------

    def _build_commits(self, dg: graphviz.Digraph, graph: RepoGraph) -> None:
        hl = graph.hash_length
        rendered_commits: set[str] = set()

        for ref in graph.refs:
            ref_id = ref.path

            if ref.is_head:
                self._add_node(dg, ref_id, label="HEAD", type_key="ref")
                if graph.head_branch_path:
                    # Non-detached: HEAD → branch ref node
                    self._add_edge(dg, ref_id, graph.head_branch_path, label="HEAD")
                    # The branch ref will walk the commit chain
                    continue
                else:
                    # Detached HEAD → commit
                    self._add_edge(dg, ref_id, ref.commit_hexsha, label="HEAD")

            elif ref.is_tag and ref.tag_object_hexsha:
                # Annotated tag: ref → tag-object → commit
                self._add_node(dg, ref_id, label=ref.name, type_key="tag")
                tag_obj_id = ref.tag_object_hexsha
                self._add_node(dg, tag_obj_id, label=tag_obj_id[:hl], type_key="tag")
                self._add_edge(dg, ref_id, tag_obj_id, label="tag")
                self._add_edge(dg, tag_obj_id, ref.commit_hexsha, label="commit")

            else:
                type_key = "tag" if ref.is_tag else "ref"
                self._add_node(dg, ref_id, label=ref.name, type_key=type_key)
                edge_label = (
                    "branch" if ref.is_branch
                    else "tag" if ref.is_tag
                    else "remote"
                )
                self._add_edge(dg, ref_id, ref.commit_hexsha, label=edge_label)

            self._walk_chain(dg, graph, ref.commit_hexsha, rendered_commits, hl)

    def _walk_chain(
        self,
        dg: graphviz.Digraph,
        graph: RepoGraph,
        start_hexsha: str,
        rendered_commits: set[str],
        hl: int,
    ) -> None:
        """Walk the first-parent chain, collapsing boring runs in normal mode."""
        collapse = (self.mode == "normal")
        obj_hexsha: Optional[str] = start_hexsha
        boring_run: list[str] = []

        while obj_hexsha:
            if obj_hexsha in rendered_commits:
                if boring_run:
                    self._emit_boring_run(dg, graph, boring_run, obj_hexsha, hl, rendered_commits)
                    boring_run = []
                break

            cd = graph.commits.get(obj_hexsha)
            if cd is None:
                if boring_run:
                    self._emit_boring_run(dg, graph, boring_run, None, hl, rendered_commits)
                    boring_run = []
                break

            next_hexsha = cd.parents[0] if cd.parents else None

            if collapse and self._is_boring(obj_hexsha, graph):
                boring_run.append(obj_hexsha)
            else:
                # Flush any accumulated boring run before this interesting commit
                if boring_run:
                    self._emit_boring_run(dg, graph, boring_run, obj_hexsha, hl, rendered_commits)
                    boring_run = []

                rendered_commits.add(obj_hexsha)
                self._add_commit_node(dg, graph, obj_hexsha, hl)

                # Edges to all parents
                for parent_hexsha in cd.parents:
                    self._add_edge(dg, obj_hexsha, parent_hexsha, label="parent")

                # Recursively walk non-first parents (merge sources not on any ref)
                for parent_hexsha in cd.parents[1:]:
                    if parent_hexsha not in rendered_commits:
                        self._walk_chain(dg, graph, parent_hexsha, rendered_commits, hl)

            # End-of-chain flush
            if next_hexsha is None and boring_run:
                self._emit_boring_run(dg, graph, boring_run, None, hl, rendered_commits)
                boring_run = []

            obj_hexsha = next_hexsha

    def _emit_boring_run(
        self,
        dg: graphviz.Digraph,
        graph: RepoGraph,
        run: list[str],
        next_hexsha: Optional[str],
        hl: int,
        rendered_commits: set[str],
    ) -> None:
        """Emit a boring run as a single commit or a collapsed summary node."""
        for hexsha in run:
            rendered_commits.add(hexsha)

        if len(run) == 1:
            self._add_commit_node(dg, graph, run[0], hl)
        else:
            first, last = run[0], run[-1]
            label = f"{last[:hl]} ({len(run)}) {first[:hl]}"
            self._add_node(dg, first, label=label, type_key="commit_summary")

        if next_hexsha:
            self._add_edge(dg, run[0], next_hexsha, label="parent")

    def _add_commit_node(
        self, dg: graphviz.Digraph, graph: RepoGraph, hexsha: str, hl: int
    ) -> None:
        """Add a single commit node, with optional detail lines."""
        cd = graph.commits.get(hexsha)
        label = hexsha[:hl]
        if self.commit_details and cd:
            msg = cd.short_message[:40] + ("…" if len(cd.short_message) > 40 else "")
            label = "\n".join([label, cd.author, msg, cd.date_iso[:10]])

        self._add_node(dg, hexsha, label=label, type_key="commit")

        if self.mode == "verbose" and cd and cd.tree_hexsha:
            self._add_tree_recursive(dg, graph, cd.tree_hexsha, hexsha, hl)

    def _add_tree_recursive(
        self,
        dg: graphviz.Digraph,
        graph: RepoGraph,
        tree_hexsha: str,
        parent_id: str,
        hl: int,
    ) -> None:
        """Recursively add tree and blob nodes for verbose mode."""
        if tree_hexsha in self._rendered_nodes:
            # Tree already drawn; still need the edge from this parent
            self._add_edge(dg, parent_id, tree_hexsha, label="tree")
            return

        td = graph.trees.get(tree_hexsha)
        if td is None:
            return

        self._add_node(dg, tree_hexsha, label=tree_hexsha[:hl], type_key="tree")
        self._add_edge(dg, parent_id, tree_hexsha, label="tree")

        for blob_hexsha in td.blob_hexshas:
            bd = graph.blobs.get(blob_hexsha)
            if bd:
                blob_label = f"{bd.name}\n{blob_hexsha[:hl]}"
                self._add_node(dg, blob_hexsha, label=blob_label, type_key="blob")
                self._add_edge(dg, tree_hexsha, blob_hexsha, label=bd.name)

        for child_tree_hexsha in td.child_tree_hexshas:
            self._add_tree_recursive(dg, graph, child_tree_hexsha, tree_hexsha, hl)

    # ------------------------------------------------------------------
    # Index / working tree (verbose mode only)
    # ------------------------------------------------------------------

    def _build_index(
        self, dg: graphviz.Digraph, graph: RepoGraph, index_state: IndexState
    ) -> None:
        hl = graph.hash_length

        if index_state.staged:
            self._add_node(dg, "Staged Changes", label="Staged Changes",
                           type_key="staged_changes")
            for sf in index_state.staged:
                node_id = f"staged:{sf.path}"
                label = f"{sf.path}\n{sf.hexsha[:hl]}"
                self._add_node(dg, node_id, label=label, type_key="staged_changes")
                self._add_edge(dg, "Staged Changes", node_id, label=sf.path)

        if index_state.unstaged:
            self._add_node(dg, "Unstaged Changes", label="Unstaged Changes",
                           type_key="unstaged_changes")
            for uf in index_state.unstaged:
                node_id = f"unstaged:{uf.path}"
                label = f"{uf.path}\n{uf.workspace_hexsha[:hl]}"
                self._add_node(dg, node_id, label=label, type_key="unstaged_changes")
                self._add_edge(dg, "Unstaged Changes", node_id, label=uf.path)

        if index_state.untracked:
            self._add_node(dg, "Untracked", label="Untracked",
                           type_key="untracked_file")
            for path in index_state.untracked:
                node_id = f"untracked:{path}"
                self._add_node(dg, node_id, label=path, type_key="untracked_file")
                self._add_edge(dg, "Untracked", node_id, label=path)

    # ------------------------------------------------------------------
    # Branch topology mode
    # ------------------------------------------------------------------

    def _build_branch(self, dg: graphviz.Digraph, topo: BranchTopology) -> None:
        if not topo.nodes:
            self._add_node(dg, "no-branches", label="No branches", type_key="ref")
            return

        for node in topo.nodes:
            type_key = "tag" if node.is_tag else "ref"
            label = node.name
            if node.is_head:
                label = f"HEAD→{node.name}"
            self._add_node(dg, node.name, label=label, type_key=type_key)

        # Fork commit nodes — shown as commit-style nodes labelled with short hash
        for fork in topo.fork_commits:
            label = f"fork\n{fork.short_hexsha}"
            self._add_node(dg, fork.hexsha, label=label, type_key="commit")

        if topo.head_commit:
            self._add_node(dg, "HEAD", label="HEAD (detached)", type_key="ref")

        for edge in topo.edges:
            self._add_edge(dg, edge.from_id, edge.to_name, label="")

    # ------------------------------------------------------------------
    # Low-level node/edge helpers
    # ------------------------------------------------------------------

    def _is_boring(self, hexsha: str, graph: RepoGraph) -> bool:
        """A commit is boring if it has exactly 1 parent, 1 child, and 0 refs."""
        cd = graph.commits.get(hexsha)
        if cd is None:
            return False
        return len(cd.parents) == 1 and len(cd.children) == 1 and len(cd.refs) == 0

    def _colors_for(self, node_id: str, type_key: str) -> NodeColors:
        """Return colors, substituting highlight colors for new nodes."""
        if node_id in self.highlight_ids:
            return SCHEME["new_node"]
        return SCHEME.get(type_key, SCHEME["commit"])

    def _add_node(
        self, dg: graphviz.Digraph, node_id: str, label: str, type_key: str
    ) -> None:
        if node_id in self._rendered_nodes:
            return
        self._rendered_nodes.add(node_id)
        colors = self._colors_for(node_id, type_key)
        dg.node(
            node_id,
            label=label,
            color=colors.line,
            fillcolor=colors.fill,
            style="filled",
            penwidth="2",
        )

    def _add_edge(
        self, dg: graphviz.Digraph, from_id: str, to_id: str, label: str = ""
    ) -> None:
        key = (from_id, to_id)
        if key in self._rendered_edges:
            return
        self._rendered_edges.add(key)
        dg.edge(from_id, to_id, label=label)
