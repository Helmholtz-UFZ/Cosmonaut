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

# Run with visible browser
./run_pytest.sh --headed

# Generate Playwright test
./run_codegen_test.sh
```

**Important:** Always use `./run_pytest.sh` (without `--no-services`) to verify changes.
The `--no-services` flag is only for faster iteration when you already have
services running in a separate terminal. See [Testing](docs/conventions/testing.md).

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
