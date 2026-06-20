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
| `tests/conftest.py` | Shared pytest fixtures (in-memory git repos via GitPython) |
| `tests/test_builder.py` | Main test suite — 53+ tests covering all three modes |

## Key conventions

- All git access goes through `gitplot/repo.py` — never call GitPython directly from `builder.py` or `renderer.py`.
- Tests build real in-memory git repos using `git.Repo.init()` in a `tmp_path` fixture — no mocking of git operations.
- Helper functions `node_in(source, id)` and `edge_in(source, from_id, to_id)` are in `conftest.py` for asserting DOT source content.
- `_BRANCH_PRIORITY` in `repo.py` defines which branch is "parent" when two branches share the same commit SHA (used in branch topology).
- Boring commit collapse: a commit with one parent, one child, and no refs is collapsed into a summary node showing `LAST (N) FIRST`.

## Merge methods reminder

| PR | GitHub merge button to use |
|----|---------------------------|
| `feature/*` → `develop` | **Squash and merge** |
| `develop` → `main` | **Create a merge commit** |
