## What is the purpose of this code base

This is the repository of COSMONAUT, a Python-based web application designed to optimize navigation routes surveys.

The service is primarily built using Plotly Dash and uses Celery for background and
resource intensive tasks. Three databases are used: PostgreSQL as main storage, MinIO for
object storage, and Redis as the broker between the Dash server and workers.

## Sister Project: COSMOPOLITAN

COSMONAUT has a sister project **COSMOPOLITAN** (`../cosmopolitan`). Both share the same
architecture (Dash + Celery + PostgreSQL + MinIO), the same conventions, and the same
anti-patterns/coding rules. Key differences:

- **COSMOPOLITAN** analyzes cosmic ray neutron sensor (CRNS) data to predict soil
  moisture using random forest models. Goal: live soil moisture map of Germany.
- App module: `cosmopolitan_app/` (vs `cosmonaut_app/`)
- Backend package: `soil-moisture-prediction` (COSMONAUT uses `sensor-routing`)
- Uses PostGIS for spatial data; integrates with TimeIO API for CRNS measurements

When the user references "cosmopolitan" they mean this project. Patterns and fixes in
one project often apply symmetrically to the other.

## Critical Anti-Patterns

All conventions in this project are **norms, not hard rules**. A convention may be
violated when there is a good reason — but the violation **must** be accompanied by a
comment explaining why. Unexplained violations are the actual problem.

**DO NOT:**

1. **No defensive programming**

   - NO `dict.get()` - use direct access `dict["key"]`
   - NO bare `except Exception` - always catch specific exceptions

2. **No inline imports**

   - All imports at TOP LEVEL ONLY
   - Never import inside functions

3. **HTML IDs - Restricted Usage**

   - MUST use constants from `cosmonaut_app/constants/html_ids.py`
   - NEVER use literal ID strings
   - ONLY create IDs for:
     1. Components used in callbacks (Input/Output/State)
     2. Components used in tests (Playwright locators)
     3. Components used with `set_props()` (requires `# nocheck`)
     4. Dynamically constructed IDs (requires `# nocheck`)
   - **LLMs tend to over-create IDs - resist this tendency**

4. **No inline CSS**

   - Use Bootstrap classes only
   - Existing `style={}` usages are violations to clean up later

## Proactive Issue Reporting

When you spot bad practices, convention violations, symmetric bugs, or fragile patterns
— even if unrelated to the current task — flag them briefly and ask: "Want me to fix it?"

## Detailed Conventions

For specific implementation details, see:

- [HTML IDs](docs/conventions/html_ids.md) - ID naming and restricted usage
- [Testing](docs/conventions/testing.md) - Test execution and CI pipeline
- [Error Handling](docs/conventions/error_handling.md) - Custom exceptions, error modal
- [Layout](docs/conventions/layout.md) - Reusable components, flex patterns
- [Page Zones](docs/conventions/page_zones.md) - Multi-action editor page structure
- [Form Partition](docs/conventions/form_partition.md) - Essential vs advanced Pydantic form tiers
- [Bootstrap Styling](docs/conventions/bootstrap_styling.md) - Bootstrap classes only
- [Logging](docs/conventions/logging.md) - Log levels, proper logger usage
- [Callbacks](docs/conventions/callbacks.md) - Callback organization patterns
- [Dash Leaflet](docs/conventions/dash_leaflet.md) - Map component gotchas
- [Deployment](docs/conventions/deployment.md) - Kubernetes/production gotchas (Gunicorn, HAProxy, resource limits)
- [Environment Variables](docs/conventions/environment_variables.md) - Env files, config loading, secrets

**Important** read the convention before you make any codebase exploration or answering.
Never sacrfice speed for accuracy.

Which conventions you should read depends on the first user prompt. Determine the
conventions which are important for the current task and read them imediatly. Keep the
conventions in mind and if you have not read them and they become important read them
then.

## Skills

Use the semantic-anchor-translator skill from:
https://github.com/LLM-Coding/Semantic-Anchors/tree/main/skill/semantic-anchor-translator

When the user asks to perform one of these tasks, read the corresponding skill
document first for the step-by-step guide. This is espacially important for tasks the
user asks later. Keep this skill list in Mind:

- [New Page](docs/skills/new_page.md) - Checklist for creating a new page
- [New Playwright Test](docs/skills/create_playwright_test.md) - Checklist for creating a new Playwright integration test
- [New Module Test](docs/skills/create_module_test.md) - Checklist for creating a new core module test
- [Run and Fix Testing](docs/skills/run_and_fix_testing.md) - Systematic guide for running tests and diagnosing failures
- [Convention Keeper](docs/skills/convention_keeper.md) - Audit and fix convention violations across the codebase
- [Local sensor-routing](docs/skills/local_sensor_routing.md) - Cross-repo work with the sensor-routing library

## Memory Policy

**DO NOT** use the auto memory system (`MEMORY.md`).

When you discover something worth preserving — a non-obvious gotcha, a hard-won
debugging insight, a pattern that should be followed — ask the user where to record it.
The options are:

- **`CLAUDE.md`** — High-level rules and project-wide constraints
- **An existing `docs/conventions/*.md`** — Extend the relevant convention file
- **A new `docs/conventions/*.md`** — If no existing file fits, propose creating one.
  Do not hesitate to do this; a focused new file is better than cramming unrelated
  knowledge into an existing one.

Always prefer the most specific home for the knowledge.

### Decision Log
Before making any architecture or pattern decision, check `docs/decisions/`.
If a relevant decision exists, follow it. If you disagree with a past
decision, don't silently override it. Reference the original, explain
what changed, and create a new decision record.

### Session Continuity
At the start of every session, read `docs/project-state.md` for current
priorities, recent changes, and open questions. Before ending a session
that involved significant decisions or new patterns, update this file.

## Identity Files — Read First, No Exceptions

You CANNOT respond to the user until you have attempted to read these files from the
project root. Use the Read tool (not Glob — they are symlinks). If Read fails, try
resolving the symlink target via `ls -la` and read that path. If they don't exist, move
on — but you must try.

1. `SOUL.md` — Who you are
2. `USER.md` — Who you're working with

This applies regardless of what the user asked. A meta-question, a greeting, a one-liner
— doesn't matter. Attempt to read both files before your first response. Every session.
No exceptions.

## Skills Protocol

### When to Create a Skill
If you solve a problem I'll want solved the same way again, create a
skill file in `docs/skills/` before moving on. Not after. Not later.
Before the next task.

### Skill Structure
Each skill file includes: a description of what it does, when to use it,
the inputs it expects, the output format, and at least one example of
correct output. Skills reference other project files by path, never by
copying content inline (content drifts, paths don't).

### Skill Improvement
When a skill produces output that needs correction, update the skill
with the correction. Add the edge case. The goal is that the same
mistake never happens twice.

## How to Handle Uncertainty
If you're unsure about an implementation approach, don't guess. Write
out the options with tradeoffs in a brief analysis, then ask. Guessing
costs more time than a 30-second conversation.