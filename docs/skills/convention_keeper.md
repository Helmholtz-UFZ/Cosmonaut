# Skill: Convention Keeper

Systematic audit of the codebase against all project conventions. Checks each
convention one at a time, finds violations, asks for clarification when rules are
ambiguous, and applies fixes with user approval.

---

## 1. Clarification Questions

Ask the user before starting:

1. **Scope** — Audit all conventions (Critical Anti-Patterns + detailed convention docs), or only the Critical Anti-Patterns from `CLAUDE.md`?
2. **Mode** — Audit + Fix (find violations and fix them), or audit-only (report without changing code)?
3. **Exclusions** — Any files or directories to skip? Default scope is `cosmonaut_app/**/*.py` (excludes `test/`, `docs/`, generated files).

---

## 2. Step-by-step Checklist

### Step 1: Read all convention documents

Load the current rules by reading each convention doc:

- `docs/conventions/html_ids.md`
- `docs/conventions/testing.md`
- `docs/conventions/error_handling.md`
- `docs/conventions/layout.md`
- `docs/conventions/bootstrap_styling.md`
- `docs/conventions/logging.md`
- `docs/conventions/callbacks.md`
- `docs/conventions/environment_variables.md`

### Step 2: Create the TODO list

Use `TaskCreate` to create one task per convention from the Convention Checklist
(Section 3). There are 13 conventions total. Each task subject should be the
convention name (e.g. "No dict.get()") and the description should include the
search patterns from the checklist.

### Step 3: Work through each convention (loop)

For each TODO item, perform these sub-steps:

**a. Mark in-progress**

`TaskUpdate` status → `in_progress`.

**b. Explore the codebase**

Use an **Explore subagent** with the search patterns from Section 3 to find
violations. Provide the subagent with:
- The exact grep/glob patterns from the checklist row
- The target file scope
- Instructions to list every violation with file path and line number

**c. Evaluate findings**

Review each violation the subagent reports. If the convention is ambiguous or a
finding is borderline:

- Use `AskUserQuestion` to clarify with the user.
- After the user answers, update the TODO task description with the clarification
  note so it is captured for future reference. This makes the convention clearer
  for next time.

**d. Present fix plan**

Show the user the list of violations with:
- File path and line number
- Current code (the violation)
- Proposed fix

Wait for approval before proceeding.

**e. Apply fixes** (if mode is Audit + Fix)

Make the approved changes using `Edit`.

**f. Mark complete**

`TaskUpdate` status → `completed`.

**g. Clear context and proceed**

Move to the next convention. Use a **fresh Explore subagent** for the next item
to keep the main context window clean.

### Step 4: Final verification

After all conventions are done:

1. Run `./run_pytest.sh` to verify no regressions.
2. Review the task list — all items should be `completed`.
3. Report a summary to the user: how many violations found per convention, how
   many fixed, any clarifications recorded.

---

## 3. Convention Checklist

### Convention 1: No `dict.get()`

- **Source:** [CLAUDE.md](../../CLAUDE.md) §1
- **Rule:** Use direct access `dict["key"]` instead of `dict.get()`.
- **Search patterns:**
  ```
  Grep: \.get\(
  ```
- **Exclude false positives:** `.env.get`, `request.args.get`, `request.form.get`, `os.environ.get`, `session.get`, `celery_app.conf.get`. Only flag dictionary `.get()` calls in application logic.
- **Target:** `cosmonaut_app/**/*.py`

### Convention 2: No bare `except`

- **Source:** [CLAUDE.md](../../CLAUDE.md) §1
- **Rule:** Always catch specific exceptions. No `except Exception:` or bare `except:`.
- **Search patterns:**
  ```
  Grep: except Exception:
  Grep: except\s*:
  ```
- **Note:** `except Exception as e:` with re-raise (`raise`) in background task error handlers is acceptable per `error_handling.md` Section 6.
- **Target:** `cosmonaut_app/**/*.py`

### Convention 3: No inline imports

- **Source:** [CLAUDE.md](../../CLAUDE.md) §2
- **Rule:** All imports at top level only. Never import inside functions.
- **Search patterns:**
  ```
  Grep (multiline): ^\s+(import |from .+ import )
  ```
- **How to check:** For each match, verify it is inside a function or method body (indented under `def`), not at module level.
- **Target:** `cosmonaut_app/**/*.py`

### Convention 4: HTML ID literals

- **Source:** [CLAUDE.md](../../CLAUDE.md) §3, [html_ids.md](../conventions/html_ids.md)
- **Rule:** NEVER use literal ID strings. Always use constants from `cosmonaut_app/constants/html_ids.py`.
- **Search patterns:**
  ```
  Grep: id="[a-z]
  ```
- **How to check:** Look for `id=` assignments with string literals instead of constant references. The existing test `test/test_html_id_enforcement.py` also checks this — run it:
  ```bash
  ./run_pytest.sh --no-services test/test_html_id_enforcement.py
  ```
- **Target:** `cosmonaut_app/**/*.py`

### Convention 5: No inline CSS

- **Source:** [CLAUDE.md](../../CLAUDE.md) §4, [bootstrap_styling.md](../conventions/bootstrap_styling.md)
- **Rule:** No `style={}` or `style=""`. Use Bootstrap classes only.
- **Search patterns:**
  ```
  Grep: style=
  Grep: style={
  ```
- **Target:** `cosmonaut_app/**/*.py`

### Convention 6: No legacy logging

- **Source:** [CLAUDE.md](../../CLAUDE.md) §5, [logging.md](../conventions/logging.md)
- **Rule:** DO NOT use `extra={"tag": "..."}`.
- **Search patterns:**
  ```
  Grep: extra={"tag"
  Grep: extra={'tag'
  ```
- **Target:** `cosmonaut_app/**/*.py`

### Convention 7: Proper logger setup

- **Source:** [logging.md](../conventions/logging.md)
- **Rule:** Every module that logs must use `log = logging.getLogger(__name__)`. No `print()` for application output.
- **Search patterns:**
  ```
  Grep: print\(          # find print statements
  Grep: logging\.info\(  # find direct logging module calls instead of logger instance
  Grep: logging\.debug\(
  Grep: logging\.warning\(
  Grep: logging\.error\(
  ```
- **How to check:** For each file with log calls, verify it has `log = logging.getLogger(__name__)` at module level. Flag files using `logging.info()` directly instead of `log.info()`.
- **Target:** `cosmonaut_app/**/*.py`

### Convention 8: HTML ID naming

- **Source:** [html_ids.md](../conventions/html_ids.md)
- **Rule:** Constants must follow `<NAME>_<TYPE>_<PAGE>_ID` format. Values must be kebab-case.
- **Search patterns:**
  ```
  Read: cosmonaut_app/constants/html_ids.py
  ```
- **How to check:** Review each constant. Verify:
  1. Name follows `<NAME>_<TYPE>_<PAGE>_ID` pattern
  2. Value is kebab-case equivalent
  3. TYPE is a valid component type (BUTTON, INPUT, DIV, DROPDOWN, STORE, MODAL, ALERT, LINK, LAYER)
  4. PAGE matches a known page or is SHARED/COMMON
- **Target:** `cosmonaut_app/constants/html_ids.py`

### Convention 9: HTML ID file organization

- **Source:** [html_ids.md](../conventions/html_ids.md)
- **Rule:** IDs organized in three-level hierarchy: PAGE → TYPE → NAME (alphabetical within each level). SHARED/COMMON first.
- **Search patterns:**
  ```
  Read: cosmonaut_app/constants/html_ids.py
  ```
- **How to check:** Verify the file follows the grouping order. SHARED section first, then page-specific sections alphabetically.
- **Target:** `cosmonaut_app/constants/html_ids.py`

### Convention 10: Callback conventions

- **Source:** [callbacks.md](../conventions/callbacks.md)
- **Rule:**
  - Page-specific callbacks use `@callback` in page files.
  - Shared callbacks use `@app.callback` inside registration functions in `layout.py`.
  - User-triggered actions should have `prevent_initial_call=True`.
- **Search patterns:**
  ```
  Grep: @callback       # in page files
  Grep: @app.callback   # should only be in layout.py or app.py
  Grep: n_clicks        # callbacks with n_clicks should have prevent_initial_call
  ```
- **How to check:** For each callback with `n_clicks` input, verify `prevent_initial_call=True` is set. Check that `@app.callback` is not used in page files.
- **Target:** `cosmonaut_app/pages/*.py`, `cosmonaut_app/layout.py`

### Convention 11: Page file structure

- **Source:** [layout.md](../conventions/layout.md), [callbacks.md](../conventions/callbacks.md)
- **Rule:** Page files must follow this order:
  1. Module docstring
  2. Imports (standard → third-party → application)
  3. Page registration (`register_page()`)
  4. Layout function
  5. Helper functions (if needed)
  6. Callbacks section
- **Search patterns:**
  ```
  Glob: cosmonaut_app/pages/*.py
  ```
- **How to check:** Read each page file and verify the section ordering. Flag files where callbacks appear before the layout function, or imports are scattered.
- **Target:** `cosmonaut_app/pages/*.py`

### Convention 12: Error handling

- **Source:** [error_handling.md](../conventions/error_handling.md)
- **Rule:**
  - Custom exceptions defined in `error_handling.py`.
  - Every custom exception has an entry in `error_responds_dict`.
  - Guard conditions use `PreventUpdate`.
- **Search patterns:**
  ```
  Grep: class.*Exception    # find exception definitions
  Grep: class.*Error        # find error class definitions
  Grep: raise\s+\w+Error    # find custom error raises
  Grep: raise\s+\w+Exception
  ```
- **How to check:** Verify all custom exception classes are in `error_handling.py` (not scattered across other files). Check that each exception has a corresponding entry in `error_responds_dict`.
- **Target:** `cosmonaut_app/**/*.py`

### Convention 13: Environment variables

- **Source:** [environment_variables.md](../conventions/environment_variables.md)
- **Rule:**
  - All env vars accessed through `cosmonaut_app/config.py`.
  - No direct `os.getenv()` or `os.environ` outside `config.py`.
  - All vars listed in `config.env_vars`.
- **Search patterns:**
  ```
  Grep: os\.getenv\(
  Grep: os\.environ
  ```
- **Exclude:** `config.py` itself (where `getenv()` is defined).
- **How to check:** Any match outside `config.py` is a violation. Verify all vars are in `config.env_vars` list.
- **Target:** `cosmonaut_app/**/*.py`

---

## 4. Key File References

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Critical anti-patterns summary |
| `docs/conventions/*.md` | All 8 detailed convention documents |
| `cosmonaut_app/constants/html_ids.py` | HTML ID constants |
| `cosmonaut_app/config.py` | Environment config, `getenv()` wrapper |
| `cosmonaut_app/logger.py` | Logger configuration |
| `cosmonaut_app/error_handling.py` | Custom exceptions, `error_responds_dict` |
| `cosmonaut_app/layout.py` | Shared layout components and callbacks |
| `cosmonaut_app/pages/*.py` | Page files (main audit targets) |
| `test/test_html_id_enforcement.py` | HTML ID enforcement test |
| `test/test_env.py` | Environment variable completeness test |
