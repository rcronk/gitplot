# gitplot — AI assistant instructions

## What this project is

`gitplot` is a Python CLI tool that generates Graphviz (and Mermaid) visualizations of git repository structure. It has three display modes — `normal`, `verbose`, and `branch` — plus a `--monitor` mode that re-renders on every repo change.

Key packages: `gitpython` (all git access, isolated in `gitplot/repo.py`), `graphviz` (Python wrapper + system `dot` binary), `watchdog` (filesystem watcher for monitor mode).

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
pip install -e ".[dev]"       # install with dev extras
ruff check .                  # lint
ruff format --check .         # format check (use ruff format . to fix)
pytest -v                     # run all tests
```

System dependency: `graphviz` (`apt install graphviz` / `brew install graphviz`).

## Code layout

| File | Responsibility |
|------|----------------|
| `gitplot/cli.py` | Argument parsing, entry point |
| `gitplot/repo.py` | All git access via GitPython; data classes (`CommitData`, `BranchTopology`, etc.) |
| `gitplot/builder.py` | Converts repo data → Graphviz `Digraph` objects |
| `gitplot/renderer.py` | Renders the digraph to output (SVG, PNG, PDF, HTML, Mermaid) |
| `gitplot/monitor.py` | Watchdog-based monitor mode |
| `gitplot/colors.py` | Color constants and highlight logic |
| `tests/conftest.py` | Shared pytest fixtures (in-memory git repos via GitPython); `node_in`/`edge_in` DOT-source helpers |
| `tests/test_builder.py` | Structural tests — node/edge presence for all three modes and highlight logic |
| `tests/test_e2e.py` | E2E golden-file tests; run `pytest --update-golden` to regenerate after intentional output changes |
| `tests/test_monitor.py` | Monitor drain and event-filtering tests |
| `tests/test_repo.py` | GitRepo data-model unit tests |
| `tests/test_mermaid.py` | Mermaid output unit tests |
| `tests/golden/` | Reference DOT/Mermaid snapshots compared by test_e2e.py |

## Key conventions

- All git access goes through `gitplot/repo.py` — never call GitPython directly from `builder.py` or `renderer.py`.
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
