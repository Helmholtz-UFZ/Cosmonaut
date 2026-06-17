# AGENTS.md

Cross-tool entry point for AI coding agents working on **COSMONAUT** (Dash + Celery +
PostgreSQL/MinIO/Redis route-optimization app).

The canonical instructions live in **[CLAUDE.md](CLAUDE.md)** and the shared docs layer
under **[docs/](docs/README.md)**. To avoid drift, this file does not duplicate them —
read those first.

## Start here (every session)

1. **[CLAUDE.md](CLAUDE.md)** — anti-patterns, conventions index, skills, identity-file protocol.
2. **[docs/README.md](docs/README.md)** — map of the shared docs layer.
3. **[docs/architecture.md](docs/architecture.md)** — package structure and pipeline.
4. **[docs/project-state.md](docs/project-state.md)** — current priorities and recent changes.

## Non-negotiables (full detail in CLAUDE.md)

These are the rules most often violated. CLAUDE.md is authoritative if anything here is unclear.

- **No defensive programming** — direct `dict["key"]` access (no `.get()`); catch specific
  exceptions, never bare `except Exception`.
- **Imports at top level only** — never inside functions.
- **HTML IDs** come from `cosmonaut_app/constants/html_ids.py` — never literal ID strings;
  only create IDs for callbacks, tests, or `set_props`/dynamic IDs (these need `# nocheck`).
- **Bootstrap classes only** — no inline CSS.
- Any convention may be broken **with a comment explaining why** — an unexplained violation
  is the actual problem.

## Before deciding

Check **[docs/decisions/](docs/decisions/)** before making architecture/pattern decisions;
don't silently override a past decision — reference it and add a new record.

Conventions live in `docs/conventions/`, reusable task guides in `docs/skills/`.
