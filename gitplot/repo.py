"""Git repository wrapper and data model.

All GitPython usage is confined to this module; no GitPython objects leak out.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import git

log = logging.getLogger(__name__)

# Lower number = more "base" branch; used to pick edge direction when two
# branches share the same tip commit (e.g. after a fast-forward merge).
_BRANCH_PRIORITY: dict[str, int] = {"master": 0, "main": 0, "develop": 1, "dev": 1}


def _branch_priority(name: str) -> int:
    return _BRANCH_PRIORITY.get(name, 2)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class RefInfo:
    """A git reference (branch, tag, HEAD, remote) with its resolved commit."""

    path: str  # full ref path, e.g. "refs/heads/main"
    name: str  # short display name, e.g. "main"
    commit_hexsha: str
    is_head: bool = False
    is_branch: bool = False
    is_tag: bool = False
    is_remote: bool = False
    tag_object_hexsha: Optional[str] = None  # set for annotated tags


@dataclass
class CommitData:
    """Lightweight representation of a git commit."""

    hexsha: str
    parents: list[str]  # parent hexshas in order
    children: set[str] = field(default_factory=set)  # child hexshas (built post-BFS)
    refs: list[RefInfo] = field(default_factory=list)  # refs pointing here
    short_message: str = ""
    author: str = ""
    date_iso: str = ""
    tree_hexsha: Optional[str] = None  # populated in verbose mode


@dataclass
class TreeData:
    """Lightweight representation of a git tree (directory)."""

    hexsha: str
    name: str  # basename; "/" for root
    parent_hexsha: str  # parent commit or tree hexsha
    child_tree_hexshas: list[str] = field(default_factory=list)
    blob_hexshas: list[str] = field(default_factory=list)


@dataclass
class BlobData:
    """Lightweight representation of a git blob (file)."""

    hexsha: str
    name: str  # filename
    parent_tree_hexsha: str


@dataclass
class StagedFile:
    path: str
    hexsha: str  # blob SHA in the index


@dataclass
class UnstagedFile:
    path: str
    workspace_hexsha: str  # computed blob SHA of the working-tree file


@dataclass
class IndexState:
    staged: list[StagedFile]
    unstaged: list[UnstagedFile]
    untracked: list[str]


@dataclass
class BranchNode:
    name: str
    path: str
    commit_hexsha: str
    is_head: bool = False
    is_remote: bool = False
    is_tag: bool = False


@dataclass
class ForkCommitNode:
    """A commit that is the common ancestor where two branches diverged."""

    hexsha: str
    short_hexsha: str
    date_iso: str


@dataclass
class BranchEdge:
    from_id: str  # branch name OR fork commit hexsha
    to_name: str  # always a branch name
    from_is_fork: bool = False


@dataclass
class BranchTopology:
    nodes: list[BranchNode]
    fork_commits: list[ForkCommitNode]  # divergence-point commit nodes
    edges: list[BranchEdge]
    head_branch: Optional[str]  # branch name if not detached
    head_commit: Optional[str]  # hexsha if detached


@dataclass
class RepoGraph:
    """Complete traversal result consumed by GraphBuilder."""

    commits: dict[str, CommitData]
    trees: dict[str, TreeData]  # empty unless include_trees=True
    blobs: dict[str, BlobData]  # empty unless include_trees=True
    refs: list[RefInfo]  # HEAD first, then branches, tags, remotes
    head_branch_path: Optional[str]  # branch ref path when not detached
    is_detached: bool
    hash_length: int


# ---------------------------------------------------------------------------
# GitRepo
# ---------------------------------------------------------------------------


class GitRepo:
    """Wraps a git.Repo and provides the data model that GraphBuilder consumes."""

    def __init__(self, repo_path: str) -> None:
        self.path = repo_path
        try:
            self._repo = git.Repo(repo_path)
            self.valid = not self._repo.bare
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            self._repo = None
            self.valid = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_graph(
        self,
        max_depth: Optional[int] = None,
        exclude_remotes: bool = False,
        include_trees: bool = False,
    ) -> RepoGraph:
        """Traverse the repo and return a complete graph snapshot."""
        if not self.valid:
            return RepoGraph(
                commits={},
                trees={},
                blobs={},
                refs=[],
                head_branch_path=None,
                is_detached=False,
                hash_length=5,
            )

        repo = self._repo

        # HEAD state
        is_detached = repo.head.is_detached
        try:
            head_branch_path = None if is_detached else repo.head.ref.path
        except Exception:
            head_branch_path = None

        refs = self._collect_refs(exclude_remotes, include_stash=include_trees)
        if not refs:
            return RepoGraph(
                commits={},
                trees={},
                blobs={},
                refs=[],
                head_branch_path=head_branch_path,
                is_detached=is_detached,
                hash_length=5,
            )

        commits, trees, blobs = self._bfs_commits(refs, max_depth, include_trees)
        self._build_children(commits)
        self._attribute_refs(commits, refs)

        n = len(commits)
        hash_length = max(5, int(math.ceil(math.log(n) * math.log(math.e, 2) / 2))) if n > 1 else 5

        return RepoGraph(
            commits=commits,
            trees=trees,
            blobs=blobs,
            refs=refs,
            head_branch_path=head_branch_path,
            is_detached=is_detached,
            hash_length=hash_length,
        )

    def get_index_state(self) -> IndexState:
        """Return staged, unstaged, and untracked file info."""
        if not self.valid:
            return IndexState(staged=[], unstaged=[], untracked=[])

        repo = self._repo
        staged: list[StagedFile] = []
        unstaged: list[UnstagedFile] = []

        # Staged: index vs HEAD commit
        try:
            head_commit = repo.head.commit
            for diff in repo.index.diff(head_commit):
                path = diff.b_path or diff.a_path
                hexsha = diff.b_blob.hexsha if diff.b_blob else "0" * 40
                staged.append(StagedFile(path=path, hexsha=hexsha))
        except ValueError:
            # Empty repo: every index entry is staged
            for (path, _stage), entry in repo.index.entries.items():
                staged.append(StagedFile(path=path, hexsha=entry.hexsha))
        except Exception as exc:
            log.warning("Could not compute staged diff: %s", exc)

        # Unstaged: working tree vs index
        try:
            for diff in repo.index.diff(None):
                path = diff.a_path
                ws_hexsha = self._compute_blob_hash(path)
                unstaged.append(UnstagedFile(path=path, workspace_hexsha=ws_hexsha))
        except Exception as exc:
            log.warning("Could not compute unstaged diff: %s", exc)

        return IndexState(
            staged=staged,
            unstaged=unstaged,
            untracked=list(repo.untracked_files),
        )

    def get_branch_topology(self, exclude_remotes: bool = False) -> BranchTopology:
        """Compute branch ancestry relationships for branch-topology mode."""
        if not self.valid:
            return BranchTopology(
                nodes=[],
                fork_commits=[],
                edges=[],
                head_branch=None,
                head_commit=None,
            )

        repo = self._repo
        nodes: list[BranchNode] = []

        try:
            head_branch = None if repo.head.is_detached else repo.head.ref.name
            head_commit = repo.head.commit.hexsha if repo.head.is_detached else None
        except Exception:
            head_branch = None
            head_commit = None

        for branch in repo.branches:
            try:
                nodes.append(
                    BranchNode(
                        name=branch.name,
                        path=branch.path,
                        commit_hexsha=branch.commit.hexsha,
                        is_head=(head_branch == branch.name),
                    )
                )
            except Exception:
                pass

        if not exclude_remotes:
            try:
                for rref in repo.remote_refs:
                    try:
                        nodes.append(
                            BranchNode(
                                name=rref.name,
                                path=rref.path,
                                commit_hexsha=rref.commit.hexsha,
                                is_remote=True,
                            )
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        for tag in repo.tags:
            try:
                nodes.append(
                    BranchNode(
                        name=tag.name,
                        path=tag.path,
                        commit_hexsha=tag.commit.hexsha,
                        is_tag=True,
                    )
                )
            except Exception:
                pass

        for sha, label in self._collect_stash_entries():
            try:
                repo.commit(sha)
                nodes.append(
                    BranchNode(
                        name=label,
                        path=f"refs/stash/{label}",
                        commit_hexsha=sha,
                    )
                )
            except Exception:
                pass

        fork_commits, edges = self._compute_branch_topology(nodes)
        return BranchTopology(
            nodes=nodes,
            fork_commits=fork_commits,
            edges=edges,
            head_branch=head_branch,
            head_commit=head_commit,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_stash_entries(self) -> list[tuple[str, str]]:
        """Return [(sha, 'stash@{N}'), ...] newest-first from the stash reflog."""
        import os

        reflog_path = os.path.join(self._repo.git_dir, "logs", "refs", "stash")
        try:
            with open(reflog_path) as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        except OSError:
            return []
        entries = []
        for i, line in enumerate(reversed(lines)):
            parts = line.split()
            if len(parts) < 2:
                continue
            sha = parts[1]
            if len(sha) >= 40 and all(c in "0123456789abcdefABCDEF" for c in sha):
                entries.append((sha, f"stash@{{{i}}}"))
        return entries

    def _collect_refs(self, exclude_remotes: bool, include_stash: bool = False) -> list[RefInfo]:
        """Return refs in traversal order: HEAD, branches, tags, remotes."""
        repo = self._repo
        refs: list[RefInfo] = []
        seen: set[str] = set()

        # HEAD (always first)
        try:
            head_commit = repo.head.commit
        except ValueError:
            return []  # empty repo with no commits yet

        refs.append(
            RefInfo(
                path="HEAD",
                name="HEAD",
                commit_hexsha=head_commit.hexsha,
                is_head=True,
            )
        )
        seen.add("HEAD")

        # Local branches
        for branch in repo.branches:
            if branch.path not in seen:
                seen.add(branch.path)
                try:
                    refs.append(
                        RefInfo(
                            path=branch.path,
                            name=branch.name,
                            commit_hexsha=branch.commit.hexsha,
                            is_branch=True,
                        )
                    )
                except Exception:
                    pass

        # Tags
        for tag in repo.tags:
            if tag.path not in seen:
                seen.add(tag.path)
                try:
                    is_annotated = isinstance(tag.object, git.TagObject)
                    refs.append(
                        RefInfo(
                            path=tag.path,
                            name=tag.name,
                            commit_hexsha=tag.commit.hexsha,
                            is_tag=True,
                            tag_object_hexsha=tag.object.hexsha if is_annotated else None,
                        )
                    )
                except Exception:
                    pass

        # Remote refs
        if not exclude_remotes:
            try:
                for rref in repo.remote_refs:
                    if rref.path not in seen:
                        seen.add(rref.path)
                        try:
                            refs.append(
                                RefInfo(
                                    path=rref.path,
                                    name=rref.name,
                                    commit_hexsha=rref.commit.hexsha,
                                    is_remote=True,
                                )
                            )
                        except Exception:
                            pass
            except Exception:
                pass

        if include_stash:
            for sha, label in self._collect_stash_entries():
                path = f"stash/{label}"
                if path not in seen:
                    seen.add(path)
                    try:
                        repo.commit(sha)
                        refs.append(
                            RefInfo(
                                path=path,
                                name=label,
                                commit_hexsha=sha,
                            )
                        )
                    except Exception:
                        pass

        return refs

    def _bfs_commits(
        self,
        refs: list[RefInfo],
        max_depth: Optional[int],
        include_trees: bool,
    ) -> tuple[dict[str, CommitData], dict[str, TreeData], dict[str, BlobData]]:
        """Multi-source BFS from all ref tips; returns commit/tree/blob dicts."""
        repo = self._repo
        commits: dict[str, CommitData] = {}
        trees: dict[str, TreeData] = {}
        blobs: dict[str, BlobData] = {}

        visited: set[str] = set()
        queue: deque[tuple[git.Commit, int]] = deque()

        for ref in refs:
            hexsha = ref.commit_hexsha
            if hexsha not in visited:
                try:
                    commit_obj = repo.commit(hexsha)
                    queue.append((commit_obj, 0))
                except Exception as exc:
                    log.warning("Cannot resolve %s (%s): %s", ref.path, hexsha[:8], exc)

        while queue:
            commit_obj, depth = queue.popleft()
            hexsha = commit_obj.hexsha
            if hexsha in visited:
                continue
            visited.add(hexsha)

            parent_hexshas = [p.hexsha for p in commit_obj.parents]
            msg = (commit_obj.message or "").split("\n")[0][:72]

            commits[hexsha] = CommitData(
                hexsha=hexsha,
                parents=parent_hexshas,
                short_message=msg,
                author=commit_obj.author.name,
                date_iso=commit_obj.authored_datetime.isoformat(),
                tree_hexsha=commit_obj.tree.hexsha if include_trees else None,
            )

            if include_trees:
                self._collect_tree(commit_obj.tree, hexsha, trees, blobs)

            if max_depth is None or depth < max_depth:
                for parent in commit_obj.parents:
                    if parent.hexsha not in visited:
                        queue.append((parent, depth + 1))

        return commits, trees, blobs

    def _build_children(self, commits: dict[str, CommitData]) -> None:
        """Populate CommitData.children from each commit's parents list."""
        for hexsha, cd in commits.items():
            for parent_hexsha in cd.parents:
                if parent_hexsha in commits:
                    commits[parent_hexsha].children.add(hexsha)

    def _attribute_refs(self, commits: dict[str, CommitData], refs: list[RefInfo]) -> None:
        """Attach each RefInfo to the CommitData it points at."""
        for ref in refs:
            if ref.commit_hexsha in commits:
                commits[ref.commit_hexsha].refs.append(ref)

    def _collect_tree(
        self,
        tree: git.Tree,
        parent_hexsha: str,
        trees: dict[str, TreeData],
        blobs: dict[str, BlobData],
    ) -> None:
        """Recursively collect tree and blob objects (verbose mode)."""
        if tree.hexsha in trees:
            return

        trees[tree.hexsha] = TreeData(
            hexsha=tree.hexsha,
            name=tree.name or "/",
            parent_hexsha=parent_hexsha,
            child_tree_hexshas=[t.hexsha for t in tree.trees],
            blob_hexshas=[b.hexsha for b in tree.blobs],
        )

        for blob in tree.blobs:
            if blob.hexsha not in blobs:
                blobs[blob.hexsha] = BlobData(
                    hexsha=blob.hexsha,
                    name=blob.name,
                    parent_tree_hexsha=tree.hexsha,
                )

        for subtree in tree.trees:
            self._collect_tree(subtree, tree.hexsha, trees, blobs)

    def _compute_blob_hash(self, path: str) -> str:
        """Compute git's blob SHA for a working-tree file."""
        import os

        full_path = os.path.join(self._repo.working_dir, path)
        try:
            with open(full_path, "rb") as fh:
                content = fh.read()
            header = b"blob %d\0" % len(content)
            return hashlib.sha1(header + content).hexdigest()
        except OSError:
            return "?" * 40

    def _compute_branch_topology(
        self, nodes: list[BranchNode]
    ) -> tuple[list[ForkCommitNode], list[BranchEdge]]:
        """Build edges for the branch topology diagram.

        For each branch B we find its single best parent:
          1. Strict ancestor: another branch whose tip is in B's history.
             → direct branch-to-branch edge (no fork node needed).
          2. Diverged: neither is ancestor of the other, but they share a
             recent common ancestor.
             → insert a ForkCommitNode at the merge-base; edges fork→both.

        Strict ancestry always beats a diverged relationship. Among candidates
        of the same type, the most recent merge-base wins.
        """
        repo = self._repo
        branch_hexshas: set[str] = {n.commit_hexsha for n in nodes}

        # parent_map: child_name → (parent_id, is_strict_ancestor, rank_date)
        # parent_id is either a branch name or a fork hexsha.
        parent_map: dict[str, tuple[str, bool, int]] = {}
        forks: dict[str, git.Commit] = {}  # hexsha → git.Commit for fork commits

        for i, na in enumerate(nodes):
            for nb in nodes[i + 1 :]:
                if na.commit_hexsha == nb.commit_hexsha:
                    # Same tip commit: connect via a direct edge using name priority
                    # so e.g. "master" appears as parent of "develop" (not disconnected).
                    if _branch_priority(na.name) <= _branch_priority(nb.name):
                        parent, child = na, nb
                    else:
                        parent, child = nb, na
                    try:
                        date = repo.commit(parent.commit_hexsha).committed_date
                    except Exception:
                        date = 0
                    self._maybe_update_parent(parent_map, child.name, parent.name, True, date)
                    continue
                try:
                    ca = repo.commit(na.commit_hexsha)
                    cb = repo.commit(nb.commit_hexsha)
                    bases = repo.merge_base(ca, cb)
                    if not bases:
                        continue
                    base = bases[0]

                    if base.hexsha == ca.hexsha:
                        # na is a strict ancestor of nb: edge na→nb
                        self._maybe_update_parent(
                            parent_map, nb.name, na.name, True, ca.committed_date
                        )
                    elif base.hexsha == cb.hexsha:
                        # nb is a strict ancestor of na: edge nb→na
                        self._maybe_update_parent(
                            parent_map, na.name, nb.name, True, cb.committed_date
                        )
                    else:
                        # Diverged — use a fork commit node.
                        # If the fork commit happens to be a branch tip, use
                        # that branch instead to keep the graph clean.
                        if base.hexsha in branch_hexshas:
                            fork_branch = next(n for n in nodes if n.commit_hexsha == base.hexsha)
                            self._maybe_update_parent(
                                parent_map,
                                na.name,
                                fork_branch.name,
                                True,
                                base.committed_date,
                            )
                            self._maybe_update_parent(
                                parent_map,
                                nb.name,
                                fork_branch.name,
                                True,
                                base.committed_date,
                            )
                        else:
                            forks[base.hexsha] = base
                            self._maybe_update_parent(
                                parent_map,
                                na.name,
                                base.hexsha,
                                False,
                                base.committed_date,
                            )
                            self._maybe_update_parent(
                                parent_map,
                                nb.name,
                                base.hexsha,
                                False,
                                base.committed_date,
                            )
                except Exception as exc:
                    log.debug("merge_base(%s, %s) failed: %s", na.name, nb.name, exc)

        # Build edge list
        edges: list[BranchEdge] = []
        used_fork_hexshas: set[str] = set()
        for child_name, (parent_id, is_strict, _) in parent_map.items():
            is_fork = parent_id in forks
            if is_fork:
                used_fork_hexshas.add(parent_id)
            edges.append(
                BranchEdge(
                    from_id=parent_id,
                    to_name=child_name,
                    from_is_fork=is_fork,
                )
            )

        # Build fork node list (only forks actually referenced by edges)
        fork_commit_nodes: list[ForkCommitNode] = []
        for hexsha in used_fork_hexshas:
            base = forks[hexsha]
            fork_commit_nodes.append(
                ForkCommitNode(
                    hexsha=hexsha,
                    short_hexsha=hexsha[:8],
                    date_iso=base.authored_datetime.isoformat(),
                )
            )

        return fork_commit_nodes, edges

    @staticmethod
    def _maybe_update_parent(
        parent_map: dict[str, tuple[str, bool, int]],
        child_name: str,
        parent_id: str,
        is_strict: bool,
        rank_date: int,
    ) -> None:
        """Update parent_map only if this candidate is better than the current one."""
        existing = parent_map.get(child_name)
        if existing is None:
            parent_map[child_name] = (parent_id, is_strict, rank_date)
            return
        _, ex_strict, ex_date = existing
        # Strict ancestry always beats diverged; otherwise most-recent wins.
        if is_strict and not ex_strict:
            parent_map[child_name] = (parent_id, is_strict, rank_date)
        elif is_strict == ex_strict and rank_date > ex_date:
            parent_map[child_name] = (parent_id, is_strict, rank_date)
