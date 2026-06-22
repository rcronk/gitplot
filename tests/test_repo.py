"""Structural tests for GitRepo: traversal, data model, index state."""

from __future__ import annotations

import hashlib

from gitplot.repo import GitRepo

from .conftest import RepoTools

# ---------------------------------------------------------------------------
# Validity
# ---------------------------------------------------------------------------


def test_nonexistent_path():
    r = GitRepo("/this/does/not/exist/at/all")
    assert not r.valid
    graph = r.build_graph()
    assert graph.commits == {}
    assert graph.refs == []


def test_empty_repo(repo: RepoTools):
    r = GitRepo(str(repo.path))
    assert r.valid
    graph = r.build_graph()
    # Empty repo has no commits yet (HEAD → non-existent ref)
    assert graph.commits == {}


# ---------------------------------------------------------------------------
# Commit traversal
# ---------------------------------------------------------------------------


def test_single_commit(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("first")
    graph = GitRepo(str(repo.path)).build_graph()
    assert sha in graph.commits
    assert len(graph.commits) == 1


def test_linear_chain(repo: RepoTools):
    repo.write("a.txt")
    sha1 = repo.commit("c1")
    repo.write("b.txt")
    sha2 = repo.commit("c2")
    repo.write("c.txt")
    sha3 = repo.commit("c3")

    graph = GitRepo(str(repo.path)).build_graph()
    assert sha1 in graph.commits
    assert sha2 in graph.commits
    assert sha3 in graph.commits

    # Child relationships
    assert sha3 in graph.commits[sha2].children
    assert sha2 in graph.commits[sha1].children


def test_merge_commit(repo: RepoTools):
    repo.write("base.txt")
    repo.commit("base")

    repo.checkout("feature", new=True)
    repo.write("feature.txt")
    feat = repo.commit("feature-work")

    repo.checkout("main")
    repo.write("main.txt")
    main_commit = repo.commit("main-work")

    repo.merge("feature")
    merge = repo.rev_parse("HEAD")

    graph = GitRepo(str(repo.path)).build_graph()
    assert merge in graph.commits
    merge_cd = graph.commits[merge]
    # Merge commit has two parents
    assert len(merge_cd.parents) == 2
    assert main_commit in merge_cd.parents
    assert feat in merge_cd.parents


def test_detached_head(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("only")
    repo.detach(sha)

    graph = GitRepo(str(repo.path)).build_graph()
    assert graph.is_detached
    assert sha in graph.commits


def test_refs_attributed(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("first")

    graph = GitRepo(str(repo.path)).build_graph()
    cd = graph.commits[sha]
    # HEAD and main both point to this commit → at least 1 ref attributed
    assert len(cd.refs) >= 1
    paths = [r.path for r in cd.refs]
    assert "refs/heads/main" in paths


def test_head_ref_is_first(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    graph = GitRepo(str(repo.path)).build_graph()
    assert graph.refs[0].is_head


def test_max_commit_depth(repo: RepoTools):
    for i in range(5):
        repo.write(f"f{i}.txt")
        repo.commit(f"c{i}")

    graph = GitRepo(str(repo.path)).build_graph(max_depth=2)
    # With max_depth=2, we should see ≤ 3 commits (tip + 2 levels of parents)
    assert len(graph.commits) <= 3


def test_exclude_remotes_no_crash(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    # No remotes configured; should not raise
    graph = GitRepo(str(repo.path)).build_graph(exclude_remotes=True)
    assert len(graph.commits) == 1


def test_branch_refs_present(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("base")
    repo.checkout("dev", new=True)
    repo.write("b.txt")
    repo.commit("dev-work")
    repo.checkout("main")

    graph = GitRepo(str(repo.path)).build_graph()
    ref_paths = [r.path for r in graph.refs]
    assert "refs/heads/main" in ref_paths
    assert "refs/heads/dev" in ref_paths


def test_hash_length_scales(repo: RepoTools):
    # With many commits, hash_length should exceed 5
    for i in range(30):
        repo.write(f"f{i}.txt", content=f"content-{i}")
        repo.commit(f"commit {i}")
    graph = GitRepo(str(repo.path)).build_graph()
    assert graph.hash_length >= 5


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_lightweight_tag(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.tag("v1.0")
    graph = GitRepo(str(repo.path)).build_graph()
    tag_refs = [r for r in graph.refs if r.is_tag]
    assert len(tag_refs) == 1
    assert tag_refs[0].name == "v1.0"
    assert tag_refs[0].tag_object_hexsha is None


def test_annotated_tag(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.tag("v1.0", annotated=True, message="Release 1.0")
    graph = GitRepo(str(repo.path)).build_graph()
    tag_refs = [r for r in graph.refs if r.is_tag]
    assert len(tag_refs) == 1
    assert tag_refs[0].tag_object_hexsha is not None


# ---------------------------------------------------------------------------
# Index state
# ---------------------------------------------------------------------------


def test_index_staged(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.write("b.txt", content="new")
    repo._run(["git", "add", "b.txt"])
    # Don't commit — b.txt is staged

    idx = GitRepo(str(repo.path)).get_index_state()
    staged_paths = [s.path for s in idx.staged]
    assert "b.txt" in staged_paths


def test_index_unstaged(repo: RepoTools):
    repo.write("a.txt", content="original")
    repo.commit("first")
    repo.write("a.txt", content="modified")
    # Don't stage — a.txt is unstaged

    idx = GitRepo(str(repo.path)).get_index_state()
    unstaged_paths = [u.path for u in idx.unstaged]
    assert "a.txt" in unstaged_paths


def test_index_untracked(repo: RepoTools):
    repo.write("a.txt")
    repo.commit("first")
    repo.write("untracked.txt")  # not staged

    idx = GitRepo(str(repo.path)).get_index_state()
    assert "untracked.txt" in idx.untracked


# ---------------------------------------------------------------------------
# Trees and blobs (verbose mode)
# ---------------------------------------------------------------------------


def test_verbose_includes_trees(repo: RepoTools):
    repo.write("a.txt")
    sha = repo.commit("first")
    graph = GitRepo(str(repo.path)).build_graph(include_trees=True)
    cd = graph.commits[sha]
    assert cd.tree_hexsha is not None
    assert cd.tree_hexsha in graph.trees


def test_verbose_includes_blobs(repo: RepoTools):
    repo.write("a.txt", content="hello")
    repo.commit("first")
    graph = GitRepo(str(repo.path)).build_graph(include_trees=True)
    # At least one blob should exist
    assert len(graph.blobs) > 0


def test_workspace_hexsha_is_raw_blob_sha(repo: RepoTools):
    """workspace_hexsha must be the git blob SHA of the file's exact bytes.

    Use write_bytes (not write_text) to guarantee LF on all platforms; text
    mode on Windows converts \\n to \\r\\n, which changes the SHA and breaks
    cross-platform golden-file comparisons.
    """
    (repo.path / "a.txt").write_bytes(b"original content\n")
    repo.add("a.txt")
    repo.commit("first")

    new_content = b"modified content\n"
    (repo.path / "a.txt").write_bytes(new_content)

    idx = GitRepo(str(repo.path)).get_index_state()
    assert len(idx.unstaged) == 1
    uf = idx.unstaged[0]

    expected_sha = hashlib.sha1(b"blob %d\0" % len(new_content) + new_content).hexdigest()
    assert uf.workspace_hexsha == expected_sha
