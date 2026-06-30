"""An independent git-data oracle for visigit's verbose-mode graph.

This module re-derives the diagram visigit *should* produce, using a second,
simpler algorithm driven entirely by ``git`` plumbing subprocess calls -- a
completely different code path from visigit (which uses GitPython traversal in
``repo.py`` plus the builder walk).  A differential test then asserts that
visigit's verbose output equals this oracle on many repos, including randomly
generated ones.  Any divergence is a bug in visigit, a bug in the oracle, or a
genuine spec ambiguity -- all worth surfacing.

Scope: verbose mode (no boring-collapse, full object graph) on a repo that has
at least one commit and a CLEAN working tree (so visigit shows no staged/
unstaged/untracked index boxes, which this oracle intentionally does not model).

Comparison is on node IDs (full SHAs / ref paths / 'gitlink|<sha>') and
(from, to, label) edges.  Edge labels are structural strings ('parent', 'tree',
'branch', 'HEAD', 'tag', 'commit', 'remote', '', filename, dirname) -- none
depend on visigit's hash-length, so the comparison is layout-independent.

Faithful to visigit's ref policy (see GitRepo._collect_refs):
  HEAD, refs/heads/*, refs/tags/* (annotated -> via tag object), refs/remotes/*
  (excluding the symbolic origin/HEAD), FETCH_HEAD, ORIG_HEAD, MERGE_HEAD,
  CHERRY_PICK_HEAD, BISECT_HEAD, and stash entries (verbose only).
"""

from __future__ import annotations

import subprocess
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


def expected_verbose_graph(repo_path: str | Path) -> tuple[set[str], set[Edge]]:
    """Return (nodes, edges) visigit should draw for this repo in verbose mode."""
    repo = str(repo_path)
    nodes: set[str] = set()
    edges: set[Edge] = set()
    git_dir = _git_dir(repo)

    head_commit = _git(repo, "rev-parse", "HEAD").strip()
    commit_tips: set[str] = {head_commit}

    # ---- HEAD ----
    nodes.add("HEAD")
    rc, sym = _git_ok(repo, "symbolic-ref", "-q", "HEAD")
    if rc == 0:  # attached
        edges.add(("HEAD", sym.strip(), "HEAD"))
    else:  # detached
        edges.add(("HEAD", head_commit, "HEAD"))

    # ---- local branches ----
    for line in _git(
        repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"
    ).splitlines():
        path, sha = line.split()
        nodes.add(path)
        edges.add((path, sha, "branch"))
        commit_tips.add(sha)

    # ---- tags (lightweight one hop; annotated via tag object) ----
    fmt = "--format=%(refname)\t%(objecttype)\t%(objectname)\t%(*objectname)"
    for line in _git(repo, "for-each-ref", fmt, "refs/tags").splitlines():
        cols = (line.split("\t") + ["", "", "", ""])[:4]
        path, otype, objname, peeled = cols
        nodes.add(path)
        if otype == "tag":  # annotated: ref -> tag object -> commit
            commit = peeled
            nodes.add(objname)
            edges.add((path, objname, "tag"))
            edges.add((objname, commit, "commit"))
        else:  # lightweight: ref -> commit
            commit = objname
            edges.add((path, commit, "tag"))
        commit_tips.add(commit)

    # ---- remote-tracking refs (skip the symbolic origin/HEAD) ----
    for line in _git(
        repo, "for-each-ref", "--format=%(refname) %(objectname) %(symref)", "refs/remotes"
    ).splitlines():
        parts = line.split()
        path, sha = parts[0], parts[1]
        symref = parts[2] if len(parts) > 2 else ""
        if symref:  # symbolic (e.g. refs/remotes/origin/HEAD) -> visigit skips it
            continue
        nodes.add(path)
        edges.add((path, sha, "remote"))
        commit_tips.add(sha)

    # ---- FETCH_HEAD (first line, first token; must be a commit) ----
    fh = git_dir / "FETCH_HEAD"
    if fh.exists():
        lines = fh.read_text().splitlines()
        sha = lines[0].split("\t")[0].strip() if lines else ""
        if _is_sha(sha) and _obj_type(repo, sha) == "commit":
            nodes.add("FETCH_HEAD")
            edges.add(("FETCH_HEAD", sha, ""))
            commit_tips.add(sha)

    # ---- ORIG_HEAD / MERGE_HEAD / CHERRY_PICK_HEAD / BISECT_HEAD ----
    for name in ("ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "BISECT_HEAD"):
        p = git_dir / name
        if not p.exists():
            continue
        lines = p.read_text().splitlines()
        sha = lines[0].strip() if lines else ""
        if _is_sha(sha) and _obj_type(repo, sha) == "commit":
            nodes.add(name)
            edges.add((name, sha, ""))
            commit_tips.add(sha)

    # ---- stash entries (verbose only) ----
    rc, out = _git_ok(repo, "stash", "list", "--format=%gd %H")
    if rc == 0:
        for line in out.splitlines():
            label, sha = line.split()
            path = f"stash/{label}"
            nodes.add(path)
            edges.add((path, sha, ""))
            commit_tips.add(sha)

    # ---- reachable commits + parent edges (closure over ALL parents) ----
    rev = _git(repo, "rev-list", "--parents", *sorted(commit_tips)).splitlines()
    reachable: list[str] = []
    for line in rev:
        parts = line.split()
        commit, parents = parts[0], parts[1:]
        nodes.add(commit)
        reachable.append(commit)
        for parent in parents:
            edges.add((commit, parent, "parent"))

    # ---- object graph: each commit's root tree, then blobs/subtrees/gitlinks ----
    visited_trees: set[str] = set()
    for commit in reachable:
        root = _git(repo, "rev-parse", f"{commit}^{{tree}}").strip()
        nodes.add(root)
        edges.add((commit, root, "tree"))  # commit -> root tree is always "tree"
        _walk_tree(repo, root, visited_trees, nodes, edges)

    return nodes, edges


def _walk_tree(repo: str, tree: str, visited: set[str], nodes: set[str], edges: set[Edge]) -> None:
    """Add blob/subtree/gitlink nodes+edges under ``tree`` (deduped like the builder)."""
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
