# GitPlot — Requirements & Improvement Roadmap

## What GitPlot Is

GitPlot is a command-line tool that generates graphical visualizations of git repository structures using Graphviz. Given a path to a git repository, it traverses the commit graph and renders a diagram showing commits, branches, tags, trees, blobs, and working directory state (staged, unstaged, and untracked files). It can also run in monitor mode, watching the repository directory and regenerating the diagram automatically on changes.

---

## Current State

### Entry Point

```
python gitplot.py [OPTIONS]
```

### Command-Line Options (current)

| Flag | Default | Description |
|------|---------|-------------|
| `--repo-path` | `.` | Path to git repository |
| `--verbose` | off | Include tree and blob objects in visualization |
| `--max-commit-depth` | 10 | Maximum commits to traverse per ref |
| `--output-format` | `svg` | Output format: svg, pdf, png, etc. |
| `--rank-direction` | `RL` | Graph layout direction: RL, LR, TB, BT |
| `--collapse-commits` | off | Collapse linear (boring) commit chains into a single node |
| `--exclude-remotes` | off | Exclude remote-tracking references |
| `--head-only` | off | Only show HEAD |
| `--branch-diagram` | off | Show branch points (experimental, currently broken) |
| `--commit-details` | off | Include commit author and message in nodes |
| `--monitor` | off | Watch directory for changes and regenerate |

### Architecture

Single-file application (`gitplot.py`, ~615 lines) with one primary class `GitPlot` containing:

- **Pre-scan phase**: Collects all refs (HEAD, branches, tags, remotes), builds parent→child commit maps, calculates short hash length.
- **Draw phase**: Iterates refs, recursively traverses commits, adds nodes and edges to a Graphviz `Digraph`, handles collapsing, index state, and untracked files.
- **Render phase**: Graphviz renders to SVG/PDF/PNG and launches a viewer.

**Color scheme**: Nine object types get distinct HSV colors automatically (ref, tag, commit, commit_summary, tree, blob, staged_changes, unstaged_changes, untracked_file).

**Commit collapsing**: "Boring" commits (single parent, single child, no refs pointing at them) are grouped into one node labeled `FIRST_HASH (N) LAST_HASH`.

**Monitor mode**: Uses `watchdog` to watch the repo directory; sets a global flag `DIR_CHANGED` when any file system event occurs; regenerates and re-opens the graph.

### Dependencies

- `graphviz` (Python wrapper)
- `gitpython`
- `watchdog`
- `pylint`, `pep8` (dev/lint)
- Graphviz binaries must be installed separately on the system.

### Supporting Files

| File | Purpose |
|------|---------|
| `docs/tools.py` | `RepoTools` helper class for building temporary test repos |
| `docs/git_details.py` | Manual test script that builds a sample repo and runs gitplot |
| `docs/display.html` | Auto-refreshing HTML page that polls and displays SVG output |
| `tests/test_gitplot.py` | Linting-only test suite (pylint + pep8) |
| `Makefile` | `init` (pip install) and `test` (nosetests) targets |

---

## Known Issues and Gaps

1. **`--branch-diagram` is broken.** The flag exists and is documented as "experimental" but the branch diagram logic is incomplete.
2. **`--head-only` behavior is unclear.** Flag exists but its interaction with multi-ref traversal is not well-defined.
3. **No functional tests.** The only tests are linting checks. No tests verify graph generation, commit traversal, collapse logic, index handling, or monitor mode.
4. **Global mutable state.** `DIR_CHANGED` is a module-level global used for inter-thread signaling in monitor mode. Should be encapsulated.
5. **File encoding not specified.** File reads for blob hashing do not specify encoding, which can fail on non-UTF-8 files.
6. **Watchdog triggers too broadly.** Monitor mode fires on any file system event (including the output SVG being written), which can cause regeneration loops.
7. **No cleanup on error.** Intermediate `.dot` files are not removed if Graphviz fails.
8. **`docs/` is not a real docs directory.** It contains test utilities and example scripts rather than documentation.
9. **Test runner is `nosetests`**, which is unmaintained. Should migrate to `pytest`.
10. **`pep8` package is deprecated.** Should be replaced with `pycodestyle` or `ruff`.
11. **Single large class.** All logic lives in one `GitPlot` class; graph building, CLI parsing, file watching, and rendering are not separated.
12. **Output filename bug.** Output is written as `..dot.svg` instead of a sensible name.
13. **Viewer launch crashes on WSL2.** `xdg-open` is unavailable in headless WSL2; the tool crashes after writing a valid SVG.

---

## Target Architecture (rewrite)

### Module structure

```
gitplot/
  __init__.py
  cli.py          # Argument parsing, top-level orchestration
  repo.py         # GitRepo: wraps GitPython, provides data model
  builder.py      # GraphBuilder: turns repo data into a Graphviz graph
  renderer.py     # Renderer: output format, file writing, viewer launch
  monitor.py      # Monitor: watchdog setup, change-detection loop
  highlight.py    # HighlightTracker: tracks new/changed nodes between renders
```

### Module responsibilities

- **`GitRepo`** — wraps GitPython; provides commits, refs, index state, untracked files. All GitPython usage is here; no GitPython objects leak into other modules.
- **`GraphBuilder`** — pure function from `GitRepo` data to a Graphviz `Digraph`. Knows nothing about files or processes.
- **`Renderer`** — takes a `Digraph`, writes it to the configured output path, optionally launches a viewer. Handles platform differences.
- **`Monitor`** — encapsulates watchdog; uses a `threading.Event` for inter-thread signaling (replaces global `DIR_CHANGED`); filters out self-triggered events.
- **`HighlightTracker`** — in monitor mode, tracks which node IDs appeared since the previous render and passes them to `GraphBuilder` so new nodes can be styled distinctly.
- **`CLI`** — `argparse`-based entry point; wires the modules together; defines the `gitplot` console script.

### Packaging

`pyproject.toml` with a `[project.scripts]` entry point so `gitplot` is available as a command after `pip install`. The package is named `gitplot` and lives in a `gitplot/` package directory. The old single-file `gitplot.py` is removed.

---

## New CLI Design

### Primary mode selector

```
--mode {normal,verbose,branch}
```

| Mode | Description |
|------|-------------|
| `normal` | Default. Commits collapsed into chains (current `--collapse-commits` behavior, but on by default). Refs, commit chains, no trees/blobs. |
| `verbose` | Educational mode. Full detail: trees, blobs, index/staging area, untracked files. Intended for making educational videos. |
| `branch` | Branch topology view. Branch tips as nodes; edges show branched-from / merged-into relationships. No commits visible. |

### Fine-tuning flags (work within any mode)

| Flag | Default | Description |
|------|---------|-------------|
| `--repo-path PATH` | `.` | Path to git repository |
| `--output-format FORMAT` | `svg` | Output format: svg, pdf, png, etc. |
| `--output-path PATH` | `./gitplot.svg` | Where to write the output file |
| `--rank-direction DIR` | `RL` | Graph layout direction: RL, LR, TB, BT |
| `--max-commit-depth N` | unlimited | Cap traversal at N commits per ref. Default is unlimited; use to limit very large repos. |
| `--exclude-remotes` | off | Exclude remote-tracking references |
| `--commit-details` | off | Include commit author, message (and optionally date, file count) in nodes |
| `--no-open` | off | Write output file but do not launch a viewer |
| `--monitor` | off | Watch directory for changes and regenerate |
| `--viewer {html,auto,none}` | `html` | How to display output. `html`: use display.html (recommended for WSL2); `auto`: try xdg-open/start/open; `none`: write file only |

### Removed / replaced flags

| Old flag | Replacement |
|----------|-------------|
| `--verbose` | `--mode verbose` |
| `--collapse-commits` | Always on in `--mode normal`; not a flag |
| `--branch-diagram` | `--mode branch` (fully implemented, not broken) |
| `--head-only` | Removed (unclear semantics; can be revisited) |

---

## Commit Depth Strategy

The old default of 10 commits per ref was a performance guard for large repos. The rewrite will:

1. Default to **unlimited traversal** using a visited-commit set to short-circuit shared history — each commit is visited at most once regardless of how many refs reach it.
2. Provide `--max-commit-depth N` to cap traversal per ref for repos where even this is too slow.
3. If benchmarking on large repos (1000+ commits, many branches) shows that unlimited default is impractical, default to 50 with a clear `--all` / `--max-commit-depth 0` override.

Performance target: a 1000-commit repo with 20 branches should render in under 5 seconds on commodity hardware.

---

## Display Mode Specifications

### `--mode normal` (default)

- Show all refs (HEAD, branches, tags, remotes unless `--exclude-remotes`).
- Collapse "boring" commits (single parent, single child, no refs) into chain nodes labeled `FIRST_HASH (N) LAST_HASH`.
- Non-boring commits shown individually with short hash.
- Ref nodes point to their target commit.
- Merge commits shown individually (never collapsed).
- No trees, blobs, or working directory state.

### `--mode verbose` (educational)

Everything in normal mode, plus:

- **Tree objects** as child nodes of each commit.
- **Blob objects** as child nodes of each tree.
- **Staged changes** (index diff vs HEAD) as nodes connected to the index.
- **Unstaged changes** (working tree diff vs index) as nodes connected to the working tree.
- **Untracked files** shown connected to the working tree.
- In `--monitor` mode: nodes that were **added since the previous render** are highlighted with a distinct border color, making it visually clear what a git command just did to the DAG.

### `--mode branch` (topology view)

- One node per branch tip (local and remote unless `--exclude-remotes`).
- One node per tag.
- HEAD shown if detached or pointing at a branch.
- Edges represent the branched-from relationship: an edge from branch B to branch A means B's tip descends from A's tip (A is the merge-base ancestor).
- Merged-in branches (fully merged into another) shown with a distinct edge style.
- No commit nodes, no trees, no blobs.
- Handles detached HEAD (shows HEAD as a standalone node).
- Handles single-branch repos (one node, no edges).

---

## Monitor Mode

### Workflow

1. Render initial graph and write to `--output-path` (default `./gitplot.svg`).
2. Launch viewer according to `--viewer`:
   - `html`: open `display.html` (bundled with the package) in the default browser. The HTML page polls the SVG path and auto-refreshes.
   - `auto`: try `xdg-open` / `open` / `start` depending on platform; log a warning if unavailable.
   - `none`: write file only.
3. Watch the repo directory with watchdog.
4. On change: filter out events caused by gitplot's own output file; re-render and overwrite the SVG.
5. In `--mode verbose`: pass the previous render's node set to `GraphBuilder`; new nodes get a highlight style.
6. Use `threading.Event` for inter-thread signaling (replaces `DIR_CHANGED` global).

### `display.html`

The existing `docs/display.html` is a good foundation. Bundle it into the package so it's accessible as a resource. The HTML polls the SVG file at a fixed relative path and inlines it.

---

## Improvement Areas

### 1. Testing

**Goal**: A real test suite with functional and integration tests covering all main code paths.

- Migrate test runner from `nosetests` to `pytest`.
- Move `docs/tools.py` (`RepoTools`) into `tests/conftest.py` as a pytest fixture.
- Add **structural assertion tests** that inspect the Graphviz source for specific nodes and edges (not just "no exception raised").
- Test scenarios:
  - Linear commit chain (normal traversal)
  - Merge commits (diamond-shaped graph)
  - Detached HEAD
  - Empty repository
  - Non-existent repository path
  - Repository with no commits
  - Commit collapsing (normal mode)
  - Verbose mode (trees and blobs present in output)
  - Index state (staged and unstaged nodes present)
  - Untracked files
  - Remote refs included vs. excluded
  - Annotated tags
  - Branch topology mode (correct nodes and edges)
  - Highlight tracking (new nodes flagged between renders)
  - `--max-commit-depth` cap respected
- Add tests for `boring()` commit detection logic.
- Add tests for hash length calculation.
- Replace linting tests with a CI step or `Makefile` lint target; keep test file focused on functional behavior.

### 2. Refactoring

**Goal**: Improve internal structure to make the code easier to maintain, extend, and test.

- Implement the module structure described in Target Architecture.
- Eliminate `DIR_CHANGED` global; use `threading.Event`.
- Use `open(..., encoding='utf-8', errors='replace')` for blob hashing.
- Use `try/finally` or `tempfile` to clean up `.dot` intermediates on error.
- Replace `pep8` with `ruff`. Update `Makefile` to run `pytest` instead of `nosetests`.
- Move `docs/tools.py` to `tests/conftest.py`. Rename `docs/` to `examples/`.
- Fix output filename bug (currently produces `..dot.svg`).

### 3. Performance

**Goal**: Render efficiently on large repos (1000+ commits, many branches) and in monitor mode.

- **Visited-commit set**: stop traversing a commit chain once it has already been visited from any ref. This is the primary correctness and performance fix for shared history.
- **Short-circuit on depth cap**: when `--max-commit-depth N` is set, stop cleanly per ref.
- **Lazy blob hashing**: only hash blobs for files already known to be modified (index diff), not all workspace files.
- **Self-trigger filter**: exclude watchdog events for gitplot's own output file to prevent regeneration loops.
- **Cache ref list**: pre-scan is done once per render; avoid redundant GitPython calls within a single render.

### 4. Features

#### 4a. Branch Topology Mode

Implement `--mode branch` as described in Display Mode Specifications. Replace the broken `--branch-diagram` flag entirely.

#### 4b. Educational Highlight Mode

In `--mode verbose --monitor`, track node IDs between renders and apply a "new node" border style to nodes that appeared in the current render but not the previous one. This makes it visually obvious what a git command just did to the object graph — ideal for recording educational videos.

#### 4c. Better Monitor Mode

- Use `display.html` as the default viewer (works on WSL2, no `xdg-open` dependency).
- Bundle `display.html` as a package resource.
- Filter self-triggered watchdog events.

#### 4d. Commit Detail Improvements

- `--commit-details` shows author and message. Optionally add commit date and changed file count.
- Allow truncating long commit messages to a configurable character limit.

#### 4e. Output Improvements

- Fix output path to write `./gitplot.svg` (or `.pdf`, `.png`) in current working directory.
- `--output-path` flag to override location.
- `--no-open` flag to suppress viewer launch.

---

## Prioritization (rewrite order)

1. **Packaging + module structure** — `pyproject.toml`, module split, entry point. Foundation for everything else.
2. **Testing infrastructure** — pytest, `RepoTools` fixture, structural assertion helpers. Required before writing new feature code safely.
3. **Core rewrite: normal mode** — `GitRepo`, `GraphBuilder`, `Renderer`, `CLI`. Replaces current `gitplot.py`. Must pass all normal-mode tests.
4. **Verbose / educational mode** — trees, blobs, index state, untracked files.
5. **Branch topology mode** — `--mode branch`, merge-base logic.
6. **Monitor mode** — watchdog with `threading.Event`, `display.html` viewer, self-trigger filter.
7. **Highlight tracking** — new-node highlighting for educational videos.
8. **Performance validation** — benchmark on a large repo; decide whether to keep unlimited default or set 50.
9. **Polish** — commit details, `--output-path`, `--no-open`, `ruff` linting.

---

## Out of Scope (for now)

- Configuration file (`.gitplotrc`, `pyproject.toml [tool.gitplot]`). Add later if needed.
- GUI application (the HTML viewer is sufficient for interactive use).
- Git hosting integration (GitHub, GitLab PR visualization).
- Diff visualization (showing what changed between commits).
- Support for bare repositories (no working tree means no index/untracked state).
- Branch lane view (`--mode lanes`) — topology view covers the primary need; lanes can be added later.
