# Decision: Pin Ruff and Declare the Lint Rule Set Explicitly

**Date:** 2026-07-29
**Status:** Accepted
**Context:** The `0.3.1` release pipeline failed in the `lint` stage at `ruff check .`
on **unchanged code**, while the same command passed locally. Cause: `.gitlab-ci.yml`
ran `pip install --quiet ruff` **without a version**, so every pipeline installed
whatever was current — and `ruff 0.16.0` had been released. Locally the venv had
`0.7.4` (from `uv.lock`), so nothing reproduced.

## Decision

Two changes, both required:

1. **Pin the ruff version in all three places that reference it** — `.gitlab-ci.yml`
   (`ruff==0.16.0`), `pyproject.toml` dev group (`ruff>=0.16.0,<0.17`), and
   `.pre-commit-config.yaml` (`rev: v0.16.0`). Forward to 0.16.0, not back to 0.7.4.
2. **Declare the rule set explicitly** in `pyproject.toml` — there was no
   `[tool.ruff]` block at all, so the project rode on ruff's built-in defaults:

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "UP"]
```

See [conventions/linting.md](../conventions/linting.md) for the operational rules that
follow from this.

## Rationale

**Ruff's defaults are not a stable contract — in either direction.** 0.16.0 grew the
default set from 59 to 413 rules *and* dropped 18 long-standing ones: `E401`, `E402`,
`E701`, `E702`, `E703`, `E711`, `E712`, `E713`, `E714`, `E721`, `E731`, `E741`, `E742`,
`E743`, `F403`, `F405`, `F406`, `F722`. So an unpinned upgrade does not just add noise,
it **silently removes checks you had**. `== None`, `== True`, `lambda` assignment,
`import *`, imports not at top of file — all unchecked under 0.16.0's defaults.

That is why the pin alone is not the fix. A pin without an explicit `select` only
postpones the same conversation to the next upgrade, with more drift accumulated. The
explicit list is what actually decouples the project from Astral's changing opinion.

**Forward, not backward:** `0.7.4` is from 2024-11. Freezing a linter that long is
debt, and the measurements below show the upgrade is free — the explicit `select`
reproduces `0.7.4` behaviour exactly on a current binary.

**Why `I` and `UP` were added in the same change:** both are fully auto-fixable, so
they cost one command and no judgement. Import sorting in particular was enforced by
**nothing** — `ruff-format` does not sort imports, only `check --select I` does, which
is why 23 import blocks had drifted.

**Why `BLE`, `DTZ`, `SIM`, `S`, `RUF012` were *not* added:** each needs a per-site
judgement call (is this `except Exception` justified? does this naive `datetime`
actually matter?). Mixing that into a lint-config change would have buried real
decisions in a mechanical diff.

## Evidence

Version bisect against the unchanged `0.3.1` tree (`ruff check .`):

| ruff | result |
| --- | --- |
| 0.7.4, 0.8.0, 0.9.10, 0.11.13, 0.12.12, 0.13.3, 0.14.0, 0.15.0, 0.15.4 | `All checks passed!` |
| **0.16.0** | **193 errors** (111 auto-fixable) |

Enabled-rule count via `--show-settings`: **60** under 0.7.4 → **413** under 0.16.0 →
**106** with the explicit `select`.

**The swap is behaviour-preserving.** A probe file containing `x == None`, `x == True`,
`l = lambda: 1`, a mid-file `import`, and `from json import *`:

- 0.7.4 (old defaults): **9 findings** — `F401`×2, `E711`, `E712`, `E741`, `E731`, `E402`×2, `F403`
- 0.16.0 (new defaults): **3 findings** — `I001`, `F401`×2
- 0.16.0 + `select = ["E4","E7","E9","F"]`: **the same 9 findings as 0.7.4**

Prefix selection re-enables the dropped rules, so nothing was lost by upgrading.

**Migration cost:** 98 findings, **98 auto-fixed, 0 remaining**, across 25 files. Two
`--fix` passes were needed: `UP006` rewrites `List[x]` → `list[x]`, which turns the
`from typing import List` into an unused import that `F401` then removes. The 11
`UP035` findings reported as "not auto-fixable" resolve entirely through that cascade.

## Gotchas discovered

- **`UP006`/`UP045` rewrite annotations that Pydantic evaluates at runtime.** Checked
  before applying: code doing `get_origin(t) is Union` breaks on PEP-604 unions,
  because `get_origin(str | None)` is `types.UnionType`, not `typing.Union`. Neither
  this project nor `dash-form-factory` (which builds forms by introspecting the
  models) does that, and `pydantic_models.py` only needed `Dict` → `dict`, no
  `Optional` → `| None`. **Re-check this if `UP` is ever widened or the form factory
  is upgraded.**
- **0.16.0 adds `*.md` to the default file set** and formats Python code blocks inside
  Markdown. Currently 0 findings in `docs/`, but `ruff format` now reaches the docs.
- **`RUF100` flags `# noqa` for rules that are not enabled**, so the noqa comments and
  the `select` list are coupled — `test/fixtures/compare_osm_backends.py` had two
  `# noqa: E402` that became dead the moment E402 left the defaults.

## Verification

- `ruff check .` — clean, both via the venv and via the literal CI command
  (`pip install ruff==0.16.0 && ruff check .`).
- `pytest test/test_env.py test/test_html_id_enforcement.py
  test/test_sensor_routing_descriptions.py test/test_osm_transform.py --no-services`
  — 16 passed (the service-free set the CI runs).
- `UserModel` builds at runtime: 21 fields, `membership_upload` resolves to
  `dict[str, Any]`.
- All 25 touched files compile.
- `uv lock --upgrade-package ruff` + `uv sync` — local venv on 0.16.0, so local and CI
  now run the identical binary.
