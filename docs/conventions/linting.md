# Linting

Ruff is the only linter and formatter. Its version is pinned and its rule set is
declared explicitly — neither is optional, and both exist for a reason: an unpinned
`pip install ruff` once broke a release pipeline on unchanged code. Background:
[decisions/20260729-explicit-ruff-ruleset.md](../decisions/20260729-explicit-ruff-ruleset.md).

## Rules

- **Never rely on ruff's built-in defaults.** The active rule set lives in
  `[tool.ruff.lint] select` in `pyproject.toml`. Ruff changes its defaults in minor
  releases — 0.16.0 grew them from 59 to 413 rules *and* dropped 18 others.
- **Never install ruff unpinned.** `pip install ruff` in CI installs whatever is
  current, which makes the pipeline fail on code that did not change.
- **A ruff bump touches three files. Update all three in the same commit:**
  1. `.gitlab-ci.yml` — `pip install --quiet ruff==<version>`
  2. `pyproject.toml` dev group — `ruff>=<version>,<next-minor>`
  3. `.pre-commit-config.yaml` — `rev: v<version>`
- **After bumping, run `uv lock --upgrade-package ruff && uv sync`** so the local venv
  matches CI. Diagnosing "works locally, fails in CI" starts with `ruff --version`.
- **Adding a rule group is its own commit**, separate from a version bump. Enable it,
  run `ruff check . --fix`, and resolve the remainder deliberately — do not bulk-`noqa`
  to get green.
- **`# noqa` must name its rule** (`# noqa: E402`, not a bare `# noqa`). Bare blanket
  directives suppress future rules invisibly, and `RUF100` cannot tell you which one
  mattered.
- **A `noqa` that violates a project convention needs a comment saying why** — same
  norm as everywhere else in this codebase (see CLAUDE.md § Critical Anti-Patterns).

## Examples

### Do

```toml
# pyproject.toml — the set is ours, not the tool's
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP"]
```

```python
# Streaming writer owns the handle and closes it in .close();
# a `with` block in __init__ would close the file immediately.
self._file = open(self._tmp_path, "w", encoding="utf-8")  # noqa: SIM115
```

### Don't

```yaml
# .gitlab-ci.yml — installs whatever ruff released this morning
- "pip install --quiet ruff"
```

```python
import pandas  # noqa
```

## Notes

- **Currently enabled:** `E4`/`E7`/`E9` + `F` (the pre-0.16 default set), `I` (import
  sorting), `UP` (pyupgrade). 106 rules in total.
- **Deliberately not enabled:** `BLE`, `DTZ`, `SIM`, `S`, `RUF012`. Each needs a
  per-site judgement call rather than a blanket fix. `BLE001` is the interesting one —
  it would enforce Anti-Pattern #1 from CLAUDE.md (no bare `except Exception`)
  automatically.
- **`ruff-format` does not sort imports.** That is `check --select I` only, which is
  why `I` is in the set.
- **Since 0.16.0, `*.md` is in ruff's default file set** and Python code blocks in
  Markdown get formatted. Keep it in mind before running `ruff format` over the repo.
- **`RUF100` couples noqa comments to `select`.** Narrowing the rule set turns existing
  `# noqa: XYZ` into "unused noqa" errors, so a `select` change may require a noqa
  sweep in the same commit.
- **`UP006`/`UP045` rewrite runtime-evaluated annotations.** Pydantic models are safe
  today, but code that inspects annotations with `get_origin(...) is typing.Union`
  breaks on `X | None` (that returns `types.UnionType`). Verify before widening `UP`.
