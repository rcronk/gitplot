"""Command-line interface and top-level orchestration."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .builder import GraphBuilder
from .monitor import Monitor
from .renderer import Renderer
from .repo import GitRepo


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gitplot",
        description="Generate Graphviz visualizations of git repository structure.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--repo-path",
        default=".",
        metavar="PATH",
        help="Path to the git repository (default: current directory).",
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "verbose", "branch"],
        default="normal",
        help=(
            "Display mode: 'normal' collapses boring commit chains; "
            "'verbose' shows trees, blobs and index state (educational); "
            "'branch' shows branch topology only. (default: normal)"
        ),
    )

    # Fine-tuning flags
    parser.add_argument(
        "--output-format",
        default="svg",
        metavar="FORMAT",
        help=(
            "Output format: svg, pdf, png (Graphviz), or mermaid "
            "(writes a Mermaid flowchart .md file). (default: svg)"
        ),
    )
    parser.add_argument(
        "--output-path",
        default=None,
        metavar="PATH",
        help=(
            "Where to write the output file. "
            "Defaults to gitplot.svg (or gitplot.md for --output-format mermaid)."
        ),
    )
    parser.add_argument(
        "--rank-direction",
        default=None,
        choices=["RL", "LR", "TB", "BT"],
        help=(
            "Graphviz rank direction. "
            "Default: LR for --mode branch (fork on left, tips on right); "
            "RL for normal/verbose (newest commit on right)."
        ),
    )
    parser.add_argument(
        "--max-commit-depth",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Maximum commits to traverse per ref. "
            "Default: unlimited (shared-history short-circuits automatically)."
        ),
    )
    parser.add_argument(
        "--exclude-remotes",
        action="store_true",
        help="Exclude remote-tracking references.",
    )
    parser.add_argument(
        "--commit-details",
        action="store_true",
        help="Include commit author, message, and date in commit nodes.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Write output file but do not launch a viewer.",
    )
    parser.add_argument(
        "--viewer",
        choices=["html", "auto", "none"],
        default="html",
        help=(
            "How to display the output: 'html' opens an auto-refreshing browser page "
            "(recommended for WSL2); 'auto' tries xdg-open/open/start; "
            "'none' writes the file only. (default: html)"
        ),
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Watch the repository for changes and re-render automatically.",
    )
    parser.add_argument(
        "--verbose-log",
        action="store_true",
        help="Enable verbose logging output.",
    )

    return parser.parse_args(argv)


def _render_once(
    args: argparse.Namespace,
    renderer: Renderer,
    highlight_ids: Optional[frozenset[str]] = None,
) -> frozenset[str]:
    """Build and render one snapshot; return the node IDs that were drawn."""
    repo = GitRepo(args.repo_path)

    include_trees = args.mode == "verbose"
    graph = repo.build_graph(
        max_depth=args.max_commit_depth,
        exclude_remotes=args.exclude_remotes,
        include_trees=include_trees,
    )

    index_state = repo.get_index_state() if args.mode == "verbose" else None
    branch_topology = (
        repo.get_branch_topology(args.exclude_remotes) if args.mode == "branch" else None
    )

    # Branch mode flows forward in time left→right; commit modes flow right→left.
    if args.rank_direction is not None:
        rank_direction = args.rank_direction
    elif args.mode == "branch":
        rank_direction = "LR"
    else:
        rank_direction = "RL"

    builder = GraphBuilder(
        mode=args.mode,
        rank_direction=rank_direction,
        output_format=args.output_format,
        commit_details=args.commit_details,
        highlight_ids=highlight_ids,
    )
    dg = builder.build(graph, index_state=index_state, branch_topology=branch_topology)

    renderer.render(dg)
    return builder.node_ids


def main(argv: Optional[list[str]] = None) -> None:
    args = _parse_args(argv)

    log_level = logging.DEBUG if args.verbose_log else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(message)s")

    logging.info("gitplot %s", __version__)
    logging.info("mode=%s repo=%s", args.mode, args.repo_path)

    if args.output_path is None:
        args.output_path = "gitplot.md" if args.output_format == "mermaid" else "gitplot.svg"

    viewer = "none" if args.no_open else args.viewer
    renderer = Renderer(
        output_path=args.output_path,
        output_format=args.output_format,
        viewer=viewer,
    )

    # Initial render
    node_ids = _render_once(args, renderer)
    renderer.open_viewer(Path(args.output_path))

    if not args.monitor:
        return

    # Monitor loop
    mon = Monitor(repo_path=args.repo_path, output_path=Path(args.output_path))
    mon.update(node_ids)
    mon.start()

    try:
        while True:
            mon.wait()
            logging.info("Change detected — re-rendering…")
            highlight = mon.prev_node_ids if args.mode == "verbose" else None
            node_ids = _render_once(args, renderer, highlight_ids=highlight)
            mon.update(node_ids)
    except KeyboardInterrupt:
        logging.info("Monitor stopped.")
    finally:
        mon.stop()


if __name__ == "__main__":
    main(sys.argv[1:])
