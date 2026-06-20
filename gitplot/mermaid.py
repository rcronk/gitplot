"""Convert a Graphviz DOT digraph to Mermaid flowchart syntax."""

from __future__ import annotations

import re


def dot_to_mermaid(dot_source: str) -> str:
    """Convert a DOT digraph string to a Mermaid flowchart string.

    Handles the predictable output produced by gitplot's GraphBuilder:
    quoted and unquoted node IDs, label attributes, and labelled edges.
    Node IDs containing Mermaid-unsafe characters (/, @, {, }) are
    sanitised; their display labels are preserved verbatim.
    """
    lines = dot_source.strip().splitlines()

    rankdir = "LR"
    for line in lines:
        m = re.search(r"rankdir=(\w+)", line)
        if m:
            rankdir = m.group(1)
            break

    # id_map: raw DOT id → sanitised Mermaid id (built as nodes are seen)
    id_map: dict[str, str] = {}
    node_lines: list[str] = []
    edge_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped in ("{", "}"):
            continue
        if stripped.startswith(("digraph", "graph [")):
            continue

        # Node declaration: [quoted|unquoted id] [attrs]
        node_m = re.match(
            r'^("(?:[^"\\]|\\.)*"|[A-Za-z_\-][A-Za-z0-9_\-]*)\s+\[([^\]]+)\]',
            stripped,
        )
        if node_m:
            raw_id = _strip_quotes(node_m.group(1))
            attrs = node_m.group(2)
            label_m = re.search(r'label="((?:[^"\\]|\\.)*)"', attrs)
            label = label_m.group(1) if label_m else raw_id
            safe_id = _sanitize_id(raw_id)
            id_map[raw_id] = safe_id
            node_lines.append(f'    {safe_id}["{label}"]')
            continue

        # Edge declaration: id1 -> id2  or  id1 -> id2 [attrs]
        edge_m = re.match(
            r'^("(?:[^"\\]|\\.)*"|[A-Za-z_\-][A-Za-z0-9_\-]*)'
            r"\s*->\s*"
            r'("(?:[^"\\]|\\.)*"|[A-Za-z_\-][A-Za-z0-9_\-]*)'
            r"(?:\s+\[([^\]]*)\])?",
            stripped,
        )
        if edge_m:
            raw_from = _strip_quotes(edge_m.group(1))
            raw_to = _strip_quotes(edge_m.group(2))
            attr_block = edge_m.group(3) or ""
            from_id = id_map.get(raw_from, _sanitize_id(raw_from))
            to_id = id_map.get(raw_to, _sanitize_id(raw_to))
            label_m = re.search(r'label="((?:[^"\\]|\\.)*)"', attr_block)
            edge_label = label_m.group(1) if label_m else ""
            if edge_label:
                edge_lines.append(f'    {from_id} -->|"{edge_label}"| {to_id}')
            else:
                edge_lines.append(f"    {from_id} --> {to_id}")

    parts = [f"flowchart {rankdir}"] + node_lines + edge_lines
    return "\n".join(parts) + "\n"


def _strip_quotes(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"')
    return s


def _sanitize_id(raw: str) -> str:
    """Replace Mermaid-unsafe characters with underscores."""
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)
