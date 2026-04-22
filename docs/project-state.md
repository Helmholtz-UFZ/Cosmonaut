# Project State

Read at the start of every session (see CLAUDE.md § Session Continuity). Update at the end of sessions that involved significant decisions or new patterns.

## Current priorities

_(What's actively being worked on. Short bullets, replace as work shifts.)_

- Cleanup passes on user-facing pages to improve clarity before the sensor-routing backend rework (Can, earliest May 2026).

## Recent changes

_(Most recent first. Trim older entries when they stop being load-bearing.)_

- **2026-04-22** — Street Selection page restructured into zone-based layout (filter → per-item edit → algorithmic → footer-level undo). New convention: [conventions/page_zones.md](conventions/page_zones.md).
- **2026-04-22** — Routing Parameters page split into essential + advanced tiers with `dbc.Collapse`. New convention: [conventions/form_partition.md](conventions/form_partition.md).

## Open questions

- `optimization_objective` is still a free-text input accepting `d`/`t`/`i`. Can's backend rework (earliest May 2026) is expected to clarify semantics — revisit UX then (radio/dropdown, active/inactive indicators on Time Limit / Max distance).
- `Reset all edits` on Street Selection resets per-edit state only. Unclear whether a separate "reset job to factory state" action is needed — currently that's covered by the job reset banner/modal for non-PENDING jobs.
