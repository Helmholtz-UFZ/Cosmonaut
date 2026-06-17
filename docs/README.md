# docs/ — Shared Agent Configuration

This directory contains shared configuration for AI coding agents working on cosmonaut.
Most of it is checked into the repository so all developers benefit from the same
conventions, skills, and project context.

## Structure

```
docs/
├── conventions/     — Coding conventions and patterns (one file per topic)
├── decisions/       — Architecture and pattern decision records
├── knowledge/       — Durable concept/system explanations (index.md is the map)
├── plan/            — Implementation plans (local only, gitignored)
├── skills/          — Reusable skill guides for common tasks
├── architecture.md  — Package structure and pipeline overview
├── project-state.md — Current priorities, recent changes, open questions
└── README.md        — This file
```

## Shared vs personal config

| What | Where | Checked in? |
|------|-------|-------------|
| Conventions, skills, decisions | `docs/` | Yes — shared |
| Architecture overview, project state | `docs/` | Yes — shared |
| Plans (`docs/plan/`) | `docs/plan/` | **No — gitignored, local only** |
| Identity files (SOUL.md, USER.md) | Project root | **No — gitignored, local only** |
| Personal model preferences, permissions | `~/.claude/` | No — personal |
| Memory system (MEMORY.md) | Disabled for this project | N/A |

## Identity file setup (new developers)

These files are optional but recommended for developers who regularly use AI coding agents.
They are local only and never committed to the repository.

When you start working on cosmonaut with an AI coding agent, create these two files in
the project root (they are gitignored — your versions stay local):

**`SOUL.md`** — defines the agent's persona and working style. Create or copy from a
template and edit to match your preferences.

**`USER.md`** — describes who you are to the agent. At minimum:

```markdown
# USER.md
    Name:   <your name>
    What to call them: <your preferred name>
    Timezone: <your timezone>
    Notes: <anything relevant — role, experience level, preferences>
```

The agent reads both files at the start of every session (see `CLAUDE.md` §Identity Files).

## Plans are local

`docs/plan/` is gitignored. Plans are working documents created during Meta Sessions
(see `docs/skills/meta_session.md`). The valuable outcomes of a plan — conventions,
decisions, code — are pushed to the repo. The plan file itself stays local.

## Adding shared content

- **New convention:** Create a file in `conventions/` following `TEMPLATE.md`. Add a
  link in the CLAUDE.md "Detailed Conventions" section.
- **New skill:** Create a file in `skills/`. Add a link in the CLAUDE.md "Skills" section.
- **New decision:** Create a numbered file in `decisions/` following the format in
  `decisions/README.md`.
- **New knowledge page:** Create a file under the right `knowledge/` subfolder
  (`concepts/ systems/ datasets/ runbooks/ raw/`), add it to `knowledge/index.md`, and log it in
  `knowledge/log.md`. Knowledge = durable explanations, *not* binding rules (those are conventions)
  or one-off choices (those are decisions).
