"""An independent git-data oracle for visigit's graphs.

Re-derives the diagram visigit *should* produce using a second, simpler algorithm
driven entirely by ``git`` plumbing subprocess calls -- a completely different
code path from visigit (GitPython traversal in ``repo.py`` + the builder walk).
Differential tests then assert visigit's output equals this oracle on many repos,
including randomly generated ones.  Any divergence is a bug in visigit, a bug in
the oracle, or a genuine spec ambiguity -- all worth surfacing.

Modes:
  * verbose -- full object graph (commits + trees + blobs + gitlinks), no
    boring-collapse.  Requires a CLEAN working tree (the oracle does not model
    the staged/unstaged/untracked index boxes).
  * normal  -- refs + commits + parent edges with boring-run collapse, no object
    graph and no stash.  Works on any repo with >=1 commit (clean or dirty:
    normal mode never shows index boxes).  Collapse is expressed as a declarative
    transform of the reachable DAG, NOT a re-implementation of the builder walk.
  * branch  -- topology is a visigit-specific *presentation* (fork selection,
    branch priority), so instead of reconstructing it we check independent
    INVARIANTS via ``git merge-base`` (see branch_mode_invariants).

Comparison is on node IDs (full SHAs / ref paths / 'gitlink|<sha>') and
(from, to, label) edges.  Edge labels are structural strings -- none depend on
visigit's hash-length, so the comparison is layout-independent.

Faithful to visigit's ref policy (see GitRepo._collect_refs):
  HEAD, refs/heads/*, refs/tags/* (annotated -> via tag object), refs/remotes/*
  (excluding the symbolic origin/HEAD), FETCH_HEAD, ORIG_HEAD, MERGE_HEAD,
  CHERRY_PICK_HEAD, BISECT_HEAD, and stash entries (verbose only).
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path

Edge = tuple[str, str, str]

_HEXSET = set("0123456789abcdefABCDEF")


def _git(repo: str, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.DEVNULL).decode()


def _git_ok(repo: str, *args: str) -> tuple[int, str]:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return r.returncode, r.stdout


def _is_sha(s: str) -> bool:
    return len(s) >= 40 and all(c in _HEXSET for c in s)


def _obj_type(repo: str, sha: str) -> str:
    rc, out = _git_ok(repo, "cat-file", "-t", sha)
    return out.strip() if rc == 0 else ""


def _git_dir(repo: str) -> Path:
    raw = _git(repo, "rev-parse", "--git-dir").strip()
    p = Path(raw)
    return p if p.is_absolute() else (Path(repo) / p)


def working_tree_clean(repo: str) -> bool:
    """True if there is nothing staged, unstaged, or untracked."""
    return _git(repo, "status", "--porcelain").strip() == ""


def has_commit(repo: str) -> bool:
    rc, _ = _git_ok(repo, "rev-parse", "--verify", "-q", "HEAD")
    return rc == 0


# ---------------------------------------------------------------------------
# Shared: refs + reachable commits
# ---------------------------------------------------------------------------


def _refs_and_tips(
    repo: str, include_stash: bool, exclude_remotes: bool
) -> tuple[set[str], set[Edge], set[str]]:
    """Return (ref nodes, ref edges, commit tips) per visigit's ref policy."""
    nodes: set[str] = set()
    edges: set[Edge] = set()
    git_dir = _git_dir(repo)

    head_commit = _git(repo, "rev-parse", "HEAD").strip()
    tips: set[str] = {head_commit}

    # HEAD
    nodes.add("HEAD")
    rc, sym = _git_ok(repo, "symbolic-ref", "-q", "HEAD")
    if rc == 0:
        edges.add(("HEAD", sym.strip(), "HEAD"))
    else:
        edges.add(("HEAD", head_commit, "HEAD"))

    # local branches
    for line in _git(
        repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"
    ).splitlines():
        path, sha = line.split()
        nodes.add(path)
        edges.add((path, sha, "branch"))
        tips.add(sha)

    # tags (lightweight one hop; annotated via tag object)
    fmt = "--format=%(refname)\t%(objecttype)\t%(objectname)\t%(*objectname)"
    for line in _git(repo, "for-each-ref", fmt, "refs/tags").splitlines():
        path, otype, objname, peeled = (line.split("\t") + ["", "", "", ""])[:4]
        nodes.add(path)
        if otype == "tag":  # annotated: ref -> tag object -> commit
            commit = peeled
            nodes.add(objname)
            edges.add((path, objname, "tag"))
            edges.add((objname, commit, "commit"))
        else:  # lightweight: ref -> commit
            commit = objname
            edges.add((path, commit, "tag"))
        tips.add(commit)

    # remote-tracking refs (skip symbolic origin/HEAD)
    if not exclude_remotes:
        for line in _git(
            repo, "for-each-ref", "--format=%(refname) %(objectname) %(symref)", "refs/remotes"
        ).splitlines():
            parts = line.split()
            path, sha = parts[0], parts[1]
            symref = parts[2] if len(parts) > 2 else ""
            if symref:
                continue
            nodes.add(path)
            edges.add((path, sha, "remote"))
            tips.add(sha)

    # FETCH_HEAD
    fh = git_dir / "FETCH_HEAD"
    if fh.exists():
        lines = fh.read_text().splitlines()
        sha = lines[0].split("\t")[0].strip() if lines else ""
        if _is_sha(sha) and _obj_type(repo, sha) == "commit":
            nodes.add("FETCH_HEAD")
            edges.add(("FETCH_HEAD", sha, ""))
            tips.add(sha)

    # ORIG_HEAD / MERGE_HEAD / CHERRY_PICK_HEAD / BISECT_HEAD
    for name in ("ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "BISECT_HEAD"):
        p = git_dir / name
        if not p.exists():
            continue
        lines = p.read_text().splitlines()
        sha = lines[0].strip() if lines else ""
        if _is_sha(sha) and _obj_type(repo, sha) == "commit":
            nodes.add(name)
            edges.add((name, sha, ""))
            tips.add(sha)

    # stash (verbose only)
    if include_stash:
        rc, out = _git_ok(repo, "stash", "list", "--format=%gd %H")
        if rc == 0:
            for line in out.splitlines():
                label, sha = line.split()
                path = f"stash/{label}"
                nodes.add(path)
                edges.add((path, sha, ""))
                tips.add(sha)

    return nodes, edges, tips


def _reachable(repo: str, tips: set[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Return (commits in rev-list order, {commit: [parents]}) reachable from tips."""
    reachable: list[str] = []
    parents: dict[str, list[str]] = {}
    for line in _git(repo, "rev-list", "--parents", *sorted(tips)).splitlines():
        parts = line.split()
        reachable.append(parts[0])
        parents[parts[0]] = parts[1:]
    return reachable, parents


# ---------------------------------------------------------------------------
# Verbose mode -- full object graph
# ---------------------------------------------------------------------------


def expected_verbose_graph(
    repo_path: str | Path, exclude_remotes: bool = False
) -> tuple[set[str], set[Edge]]:
    repo = str(repo_path)
    nodes, edges, tips = _refs_and_tips(repo, include_stash=True, exclude_remotes=exclude_remotes)
    reachable, parents = _reachable(repo, tips)

    for commit in reachable:
        nodes.add(commit)
        for parent in parents[commit]:
            edges.add((commit, parent, "parent"))

    visited_trees: set[str] = set()
    for commit in reachable:
        root = _git(repo, "rev-parse", f"{commit}^{{tree}}").strip()
        nodes.add(root)
        edges.add((commit, root, "tree"))  # commit -> root tree is always "tree"
        _walk_tree(repo, root, visited_trees, nodes, edges)

    return nodes, edges


def _walk_tree(repo: str, tree: str, visited: set[str], nodes: set[str], edges: set[Edge]) -> None:
    if tree in visited:
        return
    visited.add(tree)
    for line in _git(repo, "ls-tree", tree).splitlines():
        meta, name = line.split("\t", 1)
        _mode, otype, sha = meta.split()
        if otype == "blob":
            nodes.add(sha)
            edges.add((tree, sha, name))
        elif otype == "tree":  # subdirectory: edge labelled with the directory name
            nodes.add(sha)
            edges.add((tree, sha, name))
            _walk_tree(repo, sha, visited, nodes, edges)
        elif otype == "commit":  # gitlink (submodule)
            node_id = f"gitlink|{sha}"
            nodes.add(node_id)
            edges.add((tree, node_id, name))


# ---------------------------------------------------------------------------
# Normal mode -- refs + commits + parent edges, with boring-run collapse
# ---------------------------------------------------------------------------


def expected_normal_graph(
    repo_path: str | Path, exclude_remotes: bool = False
) -> tuple[set[str], set[Edge]]:
    repo = str(repo_path)
    # Normal mode: no stash, no object graph.
    nodes, edges, tips = _refs_and_tips(repo, include_stash=False, exclude_remotes=exclude_remotes)
    reachable, parents = _reachable(repo, tips)

    # Uncollapsed commit graph.
    children: dict[str, list[str]] = defaultdict(list)
    for commit in reachable:
        nodes.add(commit)
        for parent in parents[commit]:
            edges.add((commit, parent, "parent"))
            children[parent].append(commit)

    # A commit is "boring" iff exactly 1 parent, exactly 1 child, and no ref
    # targets it (ref targets == tips).  Collapse maximal runs of boring commits
    # (linear single-parent chains) into one summary node (id = the NEWEST commit
    # of the run), exactly as the builder does -- but derived declaratively here.
    boring = {
        c
        for c in reachable
        if len(parents[c]) == 1 and len(children.get(c, [])) == 1 and c not in tips
    }

    # Run heads: a boring commit whose (unique) child is NOT boring.
    for head in boring:
        child = children[head][0]
        if child in boring:
            continue  # not the newest member of its run
        # Walk down the single-parent chain while still boring.
        run = [head]
        cur = head
        while parents[cur][0] in boring:
            cur = parents[cur][0]
            run.append(cur)
        if len(run) == 1:
            continue  # a single boring commit renders as a normal commit node
        below = parents[run[-1]][0]  # ancestor just past the run (exists: boring has 1 parent)
        # Remove the collapsed interior nodes and their parent edges; add the
        # single summary -> below edge.  The summary keeps run[0]'s id.
        for i in range(len(run) - 1):
            edges.discard((run[i], run[i + 1], "parent"))
        edges.discard((run[-1], below, "parent"))
        for hidden in run[1:]:
            nodes.discard(hidden)
        edges.add((run[0], below, "parent"))

    return nodes, edges


def expected_graph(
    repo_path: str | Path, mode: str, exclude_remotes: bool = False
) -> tuple[set[str], set[Edge]]:
    """Dispatch to the verbose/normal oracle.  Branch mode is checked separately."""
    if mode == "verbose":
        return expected_verbose_graph(repo_path, exclude_remotes=exclude_remotes)
    if mode == "normal":
        return expected_normal_graph(repo_path, exclude_remotes=exclude_remotes)
    raise ValueError(f"expected_graph supports normal/verbose, not {mode!r}")


# ---------------------------------------------------------------------------
# Branch mode -- independent invariant checks (not a full reconstruction)
# ---------------------------------------------------------------------------


def local_branches(repo: str) -> set[str]:
    out = _git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return set(out.split())


def is_ancestor(repo: str, a: str, b: str) -> bool:
    """True if commit a is an ancestor of (or equal to) commit b."""
    rc, _ = _git_ok(repo, "merge-base", "--is-ancestor", a, b)
    return rc == 0


def all_merge_bases(repo: str) -> set[str]:
    """Merge-bases of every pair of ref tips shown in branch mode (candidate forks).

    Branch mode shows branches, remotes, tags, stash entries, FETCH_HEAD and the
    special pseudo-refs as nodes, so a fork commit can be the merge-base of any
    pair of those tips -- not just branch-branch pairs.
    """
    _nodes, _edges, tips = _refs_and_tips(repo, include_stash=True, exclude_remotes=False)
    ordered = sorted(tips)
    bases: set[str] = set()
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            rc, out = _git_ok(repo, "merge-base", "--all", ordered[i], ordered[j])
            if rc == 0:
                bases.update(out.split())
    return bases
