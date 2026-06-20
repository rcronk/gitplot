"""Convert a Graphviz DOT digraph to Mermaid flowchart syntax."""

from __future__ import annotations

import colorsys
import re


def dot_to_mermaid(dot_source: str) -> str:
    """Convert a DOT digraph string to a Mermaid flowchart string.

    Handles the predictable output produced by gitplot's GraphBuilder:
    quoted and unquoted node IDs, quoted and unquoted label values, HSV
    fill/stroke colours, and labelled edges.  Node IDs containing
    Mermaid-unsafe characters (/, @, {, }) are sanitised; display labels
    and colours are preserved verbatim.
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
    style_lines: list[str] = []

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
            label = _extract_label(attrs, raw_id)
            safe_id = _sanitize_id(raw_id)
            id_map[raw_id] = safe_id
            node_lines.append(f'    {safe_id}["{label}"]')

            style = _extract_style(attrs, safe_id)
            if style:
                style_lines.append(f"    {style}")
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

    parts = [f"flowchart {rankdir}"] + node_lines + edge_lines + style_lines
    return "\n".join(parts) + "\n"


def _extract_label(attrs: str, fallback: str) -> str:
    """Return the node display label from an attr string.

    graphviz quotes label values when they contain spaces or special
    characters but leaves them unquoted when they are plain identifiers
    (e.g. a short hex hash like ``a160d``).  Both forms are handled.
    """
    # Quoted: label="some text"
    m = re.search(r'label="((?:[^"\\]|\\.)*)"', attrs)
    if m:
        return m.group(1)
    # Unquoted: label=abc123  (stops at first whitespace or comma)
    m = re.search(r"\blabel=([^\s,\]]+)", attrs)
    if m:
        return m.group(1)
    return fallback


def _extract_style(attrs: str, safe_id: str) -> str:
    """Build a Mermaid style directive from DOT HSV colour attrs, or '' if absent."""
    fill_m = re.search(r'fillcolor="([^"]*)"', attrs)
    # Use word-boundary / negative lookbehind so we don't match fillcolor again
    stroke_m = re.search(r'(?<!\w)color="([^"]*)"', attrs)
    if not fill_m and not stroke_m:
        return ""
    fill_hex = _hsv_str_to_hex(fill_m.group(1)) if fill_m else "#ffffff"
    stroke_hex = _hsv_str_to_hex(stroke_m.group(1)) if stroke_m else "#000000"
    penwidth_m = re.search(r"penwidth=(\d+)", attrs)
    pw = penwidth_m.group(1) if penwidth_m else "1"
    return f"style {safe_id} fill:{fill_hex},stroke:{stroke_hex},stroke-width:{pw}px"


def _hsv_str_to_hex(hsv_str: str) -> str:
    """Convert a DOT HSV string like '0.222 1.000 1.000' to a hex colour '#rrggbb'."""
    parts = hsv_str.split()
    if len(parts) != 3:
        return "#888888"
    h, s, v = float(parts[0]), float(parts[1]), float(parts[2])
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def _strip_quotes(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"')
    return s


def _sanitize_id(raw: str) -> str:
    """Replace Mermaid-unsafe characters with underscores."""
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)
