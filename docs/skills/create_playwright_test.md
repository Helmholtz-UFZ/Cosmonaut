# Skill: Create a New Playwright Integration Test

Step-by-step checklist for adding a Playwright integration test to the COSMONAUT application.

---

## 1. Clarification Questions

Ask the user before starting:

1. **Test creation method** — Do you want to create the test **interactively** (record in browser with `run_codegen_test.sh`) or should the **AI write it** from scratch?
2. **Target page** — Which page or feature should be tested?
3. **Background tasks** — Does the page trigger async jobs? (Determines whether the `celery_worker` fixture is needed.)
4. **Scope** — Full workflow (multi-page navigation) or single-page interactions?

---

## 2. Step-by-step Checklist

### Step 1: Study existing patterns

Before writing any test code, read:

- `test/test_complete_routing_workflow.py` — end-to-end workflow reference
- `test/conftest.py` — available fixtures (`dash_app`, `celery_worker`, `logger`)
- `test/help_functions_tests.py` — `check_all_errors(page)` utility
- `cosmonaut_app/constants/html_ids.py` — available locator constants
- The page source `cosmonaut_app/pages/<page>.py` — components, IDs, callbacks

### Step 2: Create the test (choose one path)

#### Path A: Interactive recording

1. Run the interactive test generator:

   ```bash
   ./run_codegen_test.sh -o test/test_<feature>.py
   ```

2. The user interacts with the browser; Playwright generates raw test code.

3. Adopt/refactor the generated test to follow project conventions:
   - Replace hardcoded CSS selectors with HTML ID constants from `html_ids.py`
   - Add proper imports (constants, config, helpers)
   - Add `check_all_errors(page)` calls after navigation steps
   - Add correct fixture parameters (`page, dash_app` or `page, dash_app, celery_worker`)
   - Add a docstring describing what the test validates
   - Use `expect()` assertions with appropriate timeouts instead of bare waits

#### Path B: AI writes the test

1. Read the target page source (`cosmonaut_app/pages/<page>.py`) to understand:
   - Which components exist and their IDs
   - What callbacks are registered
   - What user interactions are possible

2. Read existing Playwright tests in `test/` for pattern reference.

3. Write the test file following the reference template (see Section 3).

### Step 3: Ensure HTML ID coverage

- Every component the test interacts with **MUST** have an ID constant in `html_ids.py`
- If new IDs are needed: add them following the naming convention `<NAME>_<TYPE>_<PAGE>_ID`
- Test locators **MUST** use `f"#{CONSTANT_ID}"`, never string literals
- New IDs added purely for test locators require `# nocheck` in `html_ids.py`

### Step 4: Run the test

```bash
# Run with services (always use this to verify)
./run_pytest.sh test/test_<feature>.py

# Debug with visible browser
./run_pytest.sh --headed test/test_<feature>.py
```

### Step 5: Verify CI compatibility

- Test must run headless (no `--headed` dependency)
- Test must not depend on local file paths outside `test/test_files/`
- Services (PostgreSQL, MinIO, Redis) are available in CI — no mocking
- `env_test` is used as `.env` in CI (not `env_test_local`)
- Run the full suite to check for regressions:

  ```bash
  ./run_pytest.sh
  ```

---

## 3. Reference Template

```python
"""Test <feature> functionality.

This test validates:
1. <step description>
2. <step description>
"""

from playwright.sync_api import expect

from test.help_functions_tests import check_all_errors
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    # Import only the IDs this test needs
)


def test_<feature>(page, dash_app) -> None:
    """Test <what this test validates>."""
    # Navigate to page
    page.goto(f"http://localhost:{FLASK_PORT}/<path>")
    check_all_errors(page)

    # Interact with components
    page.locator(f"#{COMPONENT_ID}").click()

    # Assert expected state
    expect(page.locator(f"#{RESULT_ID}")).to_be_visible(timeout=10000)
    check_all_errors(page)
```

**If the test needs background tasks**, add the `celery_worker` fixture:

```python
def test_<feature>(page, dash_app, celery_worker) -> None:
```

**Common patterns:**

| Pattern | Code |
|---------|------|
| Click button | `page.locator(f"#{BUTTON_ID}").click()` |
| Wait for visible | `expect(page.locator(f"#{ID}")).to_be_visible(timeout=10000)` |
| Wait for enabled | `expect(page.locator(f"#{ID}")).to_be_enabled(timeout=120000)` |
| Upload file | `page.locator(f"#{UPLOAD_ID} input[type='file']").set_input_files("test/test_files/data.csv")` |
| Fill input | `page.locator(f"#{INPUT_ID}").fill("value")` |
| Check text | `expect(page.locator(f"#{ID}")).to_contain_text("expected")` |
| Error check | `check_all_errors(page)` |

---

## 4. Key File References

| File | Purpose |
|------|---------|
| `test/test_<feature>.py` | The new test file (create) |
| `test/conftest.py` | Fixtures: `dash_app`, `celery_worker`, `logger` (read) |
| `test/help_functions_tests.py` | `check_all_errors()` utility (read) |
| `cosmonaut_app/constants/html_ids.py` | HTML ID constants for locators (read/edit) |
| `cosmonaut_app/pages/<page>.py` | The page being tested (read) |
| `docs/conventions/testing.md` | Testing conventions reference (read) |
| `.gitlab-ci.yml` | CI pipeline configuration (read) |
| `run_pytest.sh` | Local test runner with Docker services |
| `run_codegen_test.sh` | Interactive Playwright test generator |
