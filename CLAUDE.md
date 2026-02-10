# COSMONAUT LLM Development Context

Guidelines for AI assistants working on this codebase.

## Critical Anti-Patterns

**DO NOT:**

1. **No defensive programming**

   - NO `dict.get()` - use direct access `dict["key"]`
   - NO bare `except Exception` - always catch specific exceptions
   - Existing violations to be refactored later

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

5. **No legacy logging patterns**
   - DO NOT use: `extra={"tag": "..."}`
   - Use: `log = logging.getLogger(__name__)` then `log.info(...)`

---

## Project Structure

```
cosmonaut_app/
├── constants/html_ids.py   # HTML ID constants
├── pages/                  # Page layouts + callbacks (colocated)
├── layout.py               # Shared layout + callbacks
├── error_handling.py       # Custom exceptions, error modal
├── logger.py               # Logger configuration
├── app.py                  # Flask/Dash setup
└── config.py               # Environment config
```

---

## Quick Start

```bash
# Run tests locally (starts Docker services automatically)
./run_pytest.sh
```

**Important:** Always use `./run_pytest.sh` (without `--no-services`) to verify changes. See [Testing](docs/conventions/testing.md).

---

## Detailed Conventions

For specific implementation details, see:

- [HTML IDs](docs/conventions/html_ids.md) - ID naming and restricted usage
- [Testing](docs/conventions/testing.md) - Test execution and CI pipeline
- [Error Handling](docs/conventions/error_handling.md) - Custom exceptions, error modal
- [Layout](docs/conventions/layout.md) - Reusable components, flex patterns
- [Bootstrap Styling](docs/conventions/bootstrap_styling.md) - Bootstrap classes only
- [Logging](docs/conventions/logging.md) - Log levels, proper logger usage
- [Callbacks](docs/conventions/callbacks.md) - Callback organization patterns
- [Environment Variables](docs/conventions/environment_variables.md) - Env files, config loading, secrets

---

## Skills

When the user asks to perform one of these tasks, read the corresponding skill
document first for the step-by-step guide. This is espacially important for tasks the
user asks later. Keep this skill list in Mind:

- [New Page](docs/skills/new_page.md) - Checklist for creating a new page
- [New Playwright Test](docs/skills/create_playwright_test.md) - Checklist for creating a new Playwright integration test
- [New Module Test](docs/skills/create_module_test.md) - Checklist for creating a new core module test
- [Run and Fix Testing](docs/skills/run_and_fix_testing.md) - Systematic guide for running tests and diagnosing failures
- [Convention Keeper](docs/skills/convention_keeper.md) - Audit and fix convention violations across the codebase

---

## Memory Policy

**DO NOT** use the auto memory system (`MEMORY.md`). If you feel something should
be remembered across sessions, ask the user whether it should be added to this
`CLAUDE.md` file instead.
