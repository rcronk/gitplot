# Contributing to visigit

## Branch model

```
main ← develop ← feature/your-thing
```

| PR direction            | Merge method    | Why                                         |
|-------------------------|-----------------|---------------------------------------------|
| `feature/*` → `develop` | **Squash merge** | Keeps develop history clean; one commit per feature |
| `develop` → `main`      | **Merge commit** | Preserves develop's full history on main    |

## Workflow (TDD)

1. Branch from `develop`, named after the issue number:
   ```
   git switch develop
   git switch -c feature/<N>-short-description
   ```

2. **Write failing tests first** that describe the desired behaviour. Run them to confirm they fail before writing any production code.

3. Implement the minimum code to make the tests pass.

4. Push and open a PR against `develop`.

3. CI must pass before merging (lint, format, tests on Python 3.9–3.12, file-size check, CRLF check).

4. When merging the PR to `develop`, choose **Squash and merge** in GitHub's dropdown.

5. When `develop` is ready to release, open a PR from `develop` → `main` and choose **Create a merge commit**.

## Local checks

```bash
pip install -e ".[dev]"
ruff check .          # lint
ruff format --check . # formatting
pytest -v             # tests
```
