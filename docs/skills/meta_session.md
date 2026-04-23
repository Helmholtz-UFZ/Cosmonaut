# Skill: Meta Session

A Meta Session is a structured planning conversation between a developer and a strong
AI model. Its purpose is to produce a clear, actionable plan before any code is written.
This prevents the more expensive mistake of executing in the wrong direction.
NEVER EXECUTE THE PLAN IF NOT EXPLICITLY ASKED TO!

---

## When to use

Use a Meta Session when:
- Starting a substantial piece of work (new feature, refactoring, agent setup changes)
- The scope or approach is unclear
- Multiple options exist and the tradeoffs need thinking through
- You want to ensure the agent setup stays coherent (new conventions, skills, decisions)

Do not use a Meta Session for small, well-scoped tasks — just do them.

---

## The workflow

```
1. PLAN    — Developer + strong model have a conversation
             The model asks clarifying questions until scope is fully clear
             Output: a plan file saved in docs/plan/

2. EXECUTE — A cost-efficient model executes the plan
             It does the leg work: file creation, edits, research
             The developer monitors but does not hand-hold

3. REVIEW  — Developer + strong model review the execution
             Check quality, accuracy, completeness
             Fix issues or send back for another execution pass

4. ITERATE — Repeat steps 2-3 until satisfied
```

---

## Model strategy

Use the **strongest available model** for planning and review (steps 1 and 3) and the
most **cost-efficient model** that can handle the task for execution (step 2).

The strong model's job is **judgment**: scoping, prioritisation, catching errors, asking
the right questions. The efficient model's job is **volume**: reading files, writing
content, making edits according to a clear plan.

*Example (April 2026): Claude Opus for planning and review, Claude Sonnet for execution.
Model capabilities shift — what matters is the principle, not the specific names.*

---

## Plan file format

Plans live in `docs/plan/` (gitignored — local only). Use this structure:

```markdown
# Plan: <Short Title>

**Created:** YYYY-MM-DD
**Context:** <One sentence on what prompted this>

---

## Background
<Why this is needed>

## <Section per major area of work>
- [ ] Task item
- [ ] Task item

## Execution checklist
- [ ] Specific action item
```

---

## Why plans stay local

Plans are artifacts of a specific conversation. They contain checkboxes and working
notes useful during execution but become noise afterward. The valuable outcomes
(conventions, skills, decisions, code) are pushed to the repo. The plan itself stays
local in `docs/plan/`.

If a plan produces insights worth preserving, they go into:
- `docs/conventions/` — coding pattern
- `docs/decisions/` — architecture choice
- `docs/project-state.md` — current priority or open question

---

## Inputs

- A topic or area of work described by the developer
- Access to the codebase (agent should read relevant files before proposing a plan)

## Output

A plan file at `docs/plan/<descriptive-name>.md` that:
1. States the context and motivation
2. Breaks work into tiers or sections with checkbox items
3. Specifies an execution checklist of concrete actions
4. Is clear enough that a cost-efficient model can execute it without further
   clarification from the developer
