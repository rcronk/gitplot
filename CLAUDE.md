# visigit — AI assistant instructions

## What this project is

`visigit` is a Python CLI tool that generates Graphviz (and Mermaid) visualizations of git repository structure. It has three display modes — `normal`, `verbose`, and `branch` — plus a `--monitor` mode that re-renders on every repo change.

Key packages: `gitpython` (all git access, isolated in `visigit/repo.py`), `graphviz` (Python wrapper + system `dot` binary), `watchdog` (filesystem watcher for monitor mode).

## Branch model

```
main ← develop ← feature/<issue-number>-short-description
```

- Feature branches are always cut from `develop`, named after the GitHub issue number.
- PRs from `feature/*` → `develop` use **squash merge** (keep develop history clean).
- PRs from `develop` → `main` use **merge commit** (preserve develop history on main).
- No direct pushes to `develop` or `main`.

## Development workflow (TDD)

1. **Branch**: `git switch develop && git switch -c feature/<N>-short-description`
2. **Tests first**: write failing tests that describe the desired behavior before touching production code.
3. **Implement**: write the minimum code to make tests pass.
4. **Check**: `ruff check . && ruff format --check . && pytest -v`
5. **Commit**: reference the issue — `fix #6: handle shallow clone graft placeholders`
6. **PR**: open against `develop`, CI must be green, squash merge.

## Running checks locally

```bash
pip install -e ".[dev]"       # install with dev extras (includes graphifyy)
graphify update .             # build local knowledge graph (AST-only, no API key needed)
ruff check .                  # lint
ruff format --check .         # format check (use ruff format . to fix)
pytest -v                     # run all tests
```

System dependency: `graphviz` (`apt install graphviz` / `brew install graphviz`).

## Code layout

| File | Responsibility |
|------|----------------|
| `visigit/cli.py` | Argument parsing, entry point |
| `visigit/repo.py` | All git access via GitPython; data classes (`CommitData`, `BranchTopology`, etc.) |
| `visigit/builder.py` | Converts repo data → Graphviz `Digraph` objects |
| `visigit/renderer.py` | Renders the digraph to output (SVG, PNG, PDF, HTML, Mermaid) |
| `visigit/monitor.py` | Watchdog-based monitor mode |
| `visigit/colors.py` | Color constants and highlight logic |
| `tests/conftest.py` | Shared pytest fixtures (in-memory git repos via GitPython); `node_in`/`edge_in` DOT-source helpers |
| `tests/test_builder.py` | Structural tests — node/edge presence for all three modes and highlight logic |
| `tests/test_e2e.py` | E2E golden-file tests; run `pytest --update-golden` to regenerate after intentional output changes |
| `tests/test_monitor.py` | Monitor drain and event-filtering tests |
| `tests/test_repo.py` | GitRepo data-model unit tests |
| `tests/test_mermaid.py` | Mermaid output unit tests |
| `tests/test_lessons.py` | Curriculum lesson tests — key node/edge presence per episode |
| `tests/test_lessons_full.py` | Exhaustive per-lesson tests — exact full node+edge+label set-equality (read off `GraphBuilder._rendered_nodes`/`_rendered_edges`) |
| `tests/git_oracle.py` | Independent git-plumbing oracle: re-derives the expected verbose graph from `git` subprocess calls (no GitPython/builder) |
| `tests/test_oracle_differential.py` | Differential tests: visigit verbose output vs `git_oracle` over fixed scenarios + randomly generated repos |
| `tests/golden/` | Reference DOT/Mermaid snapshots compared by test_e2e.py |

## Key conventions

- All git access goes through `visigit/repo.py` — never call GitPython directly from `builder.py` or `renderer.py`.
- Tests build real in-memory git repos using `git.Repo.init()` in a `tmp_path` fixture — no mocking of git operations.
- Helper functions `node_in(source, id)` and `edge_in(source, from_id, to_id)` are in `conftest.py` for asserting DOT source content.
- `_BRANCH_PRIORITY` in `repo.py` defines which branch is "parent" when two branches share the same commit SHA (used in branch topology).
- Boring commit collapse: a commit with one parent, one child, and no refs is collapsed into a summary node showing `LAST (N) FIRST`.
- **No non-ASCII characters in source code.** Use `->`, `--`, `...` instead of `→`, `—`, `…`. The CI `checks` job does not enforce this yet, but ruff will catch them indirectly and they cause encoding issues on some terminals.
- **Node ID separator is `|`, not `:`.** The graphviz Python library's `_quote_edge()` splits on `:` and treats the suffix as a DOT port name, so any node ID with a `:` in it generates a wrong edge target. Staged/unstaged/untracked file nodes use `f"staged|{path}"` etc.
- **Golden-file updates:** after any intentional change to DOT or Mermaid output, run `pytest tests/test_e2e.py --update-golden` to regenerate the snapshots, then commit the updated files alongside the code change.

## Merge methods reminder

| PR | GitHub merge button to use |
|----|---------------------------|
| `feature/*` → `develop` | **Squash and merge** |
| `develop` → `main` | **Create a merge commit** |

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
