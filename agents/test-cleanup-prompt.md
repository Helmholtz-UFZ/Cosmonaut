# Test Cleanup Prompt

## Purpose

This prompt is designed to be given to an AI assistant to clean up newly generated Playwright tests from `run_codegen_test.sh` and integrate them into the COSMONAUT test suite according to project standards.

## How to Use

1. Generate a test using `./run_codegen_test.sh`
2. Copy the prompt above
3. Provide it to a CodeAssitent along with: "Clean up the test at `test/test_new_codegen.py`"
4. Claude will apply all transformations and create the cleaned test file

## Key Requirements Summary

1. **Section headers** grouping actions by page (`# === Page Name ===`)
2. **Replace ALL locators** (get_by_role, get_by_text, get_by_label) with ID-based locators
3. **Create missing IDs** in html_ids.py with proper naming, organization, and `# nocheck` when needed
4. **Move uploaded files** to test/test_files/
5. **Add check_all_errors()** at end of each logical page section
6. **Standardize viewport** (use value from run_codegen)
7. **Update assertions** to use ID locators
8. **Organize imports** (Playwright → test utils → html_ids)
9. **Name test** with `test_<user_journey>` pattern
10. **Create new file** at test/test\_<name>.py

## Related Files

- ID constants: `cosmonaut_app/constants/html_ids.py`
- Test helpers: `test/help_functions_tests.py`
- Enforcement test: `test/test_html_id_enforcement.py`
- HTML ID design pattern docs: `CLAUDE.md`

---

## The Prompt

I have a newly generated Playwright test that needs to be cleaned up according to COSMONAUT testing standards. Please follow these steps:

## 1. Document the User Journey

Add section header comments that group related actions by page. Format:

```python
# === Home Page ===
page.goto(f"http://localhost:{FLASK_PORT}/")
page.locator(f"#{START_JOB_BUTTON_HOME_ID}").click()

# === User Info Page ===
page.goto(f"http://localhost:{FLASK_PORT}/job/abc123/user-info")
# ... interactions ...

# === Data Upload Page ===
# ... etc ...
```

**Important**: Always import and use `FLASK_PORT` from `cosmonaut_app.config` instead of hardcoding port numbers.

Write a brief summary at the top of the test function describing the complete user journey.

## 2. Replace All Element Locators with HTML ID Constants

**Replace ALL locator patterns** with ID-based locators:

- `get_by_role("button", name="...")` → `page.locator(f"#{BUTTON_ID}")`
- `get_by_text("...")` → `page.locator(f"#{ELEMENT_ID}")`
- `get_by_label("...")` → `page.locator(f"#{INPUT_ID}")`
- `locator("body")` (for file uploads) → `page.locator(f"#{DROPZONE_ID}")`

**For each element:**

a. Check if an ID constant exists in `cosmonaut_app/constants/html_ids.py`

- Search for the element's purpose (e.g., "Next button on Data Upload page")

b. If NO constant exists:

- Create a new constant in `html_ids.py` following the naming convention:
  - Format: `<NAME>_<TYPE>_<PAGE>_ID = "name-type-page-id"`
  - Example: `NEXT_BUTTON_DATA_UPLOAD_ID = "next-button-data-upload-id"`
- Place it in the appropriate section (group by PAGE → TYPE → alphabetically by NAME)

c. If the new ID has no callback usage:

- Add `# nocheck` comment with explanation
- Example: `DROPZONE_DIV_DATA_UPLOAD_ID = "..."  # nocheck visual container for file upload`
- Reasons to use `# nocheck`:
  - Visual containers / layout-only elements
  - CSS styling targets
  - Dynamically created elements (map layers, toasts)
  - Elements used in non-callback code (error_handling.py)

d. Import the ID constant at the top of the test file:

```python
from cosmonaut_app.constants.html_ids import (
    START_JOB_BUTTON_HOME_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    # ... all IDs used in test
)
```

## 3. Fix File Upload Paths

If the test uploads files:

- Move the uploaded files to `test/test_files/` directory (create if needed)
- Update file paths in the test:

  ```python
  # Before:
  page.locator("body").set_input_files("memberships.csv")

  # After:
  page.locator(f"#{UPLOAD_DROPZONE_DIV_DATA_UPLOAD_ID}").set_input_files("test/test_files/memberships.csv")
  ```

## 4. Add Error Checking

Add `check_all_errors(page)` at the end of each logical page section (after all interactions on a page are complete, before moving to the next page).

```python
from test.help_functions_tests import check_all_errors

# === Data Upload Page ===
page.goto("...")
page.locator(f"#{UPLOAD_ID}").set_input_files("...")
page.locator(f"#{NEXT_BUTTON_DATA_UPLOAD_ID}").click()
check_all_errors(page)  # ← Add here

# === Street Selection Page ===
# ...
```

## 5. Standardize Browser Setup

**Viewport**: Use the viewport size that was set during `run_codegen_test.sh` execution (recorded in the generated test). Common values:

- `{"width": 1920, "height": 1080}` (default)
- `{"width": 1366, "height": 768}` (laptop)

**Pattern**:

```python
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    # Test actions...

    page.close()
    context.close()
    browser.close()
```

## 6. Update Assertions

Replace generic text-based assertions with ID-based checks:

```python
# Before:
expect(page.get_by_role("button", name="Start Route")).to_be_visible()

# After:
expect(page.locator(f"#{START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID}")).to_be_visible()
```

## 7. Organize Imports

Structure imports in this order:

```python
from playwright.sync_api import expect

from test.help_functions_tests import check_all_errors
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    # Alphabetically ordered ID constants
    NEXT_BUTTON_DATA_UPLOAD_ID,
    START_JOB_BUTTON_HOME_ID,
    # ...
)
```

## 8. Name the Test

Choose a descriptive name following the pattern: `test_<user_journey>`

Examples:

- `test_complete_routing_workflow`
- `test_job_creation_with_csv_upload`
- `test_street_selection_and_route_calculation`
- `test_user_registration_and_data_upload`

The name should describe the end-to-end user journey.

## 9. Create New Test File

Save the cleaned test as `test/test_<descriptive_name>.py`

Example: `test/test_complete_routing_workflow.py`

## 10. Verify

After cleanup, verify:

- [ ] All locators use ID constants from html_ids.py
- [ ] New IDs added to html_ids.py with proper naming and organization
- [ ] Unused IDs have `# nocheck` comments with explanations
- [ ] File uploads reference test/test_files/ directory
- [ ] check_all_errors() called at end of each page section
- [ ] Imports properly organized (including `FLASK_PORT` from config)
- [ ] URLs use `FLASK_PORT` instead of hardcoded port numbers
- [ ] Section headers document the page flow
- [ ] Test has descriptive name matching user journey
- [ ] Run `pytest test/test_html_id_enforcement.py` to verify ID usage is correct

## 11. Run the Test

After completing all cleanup steps, run the test to verify it works:

```bash
./run_pytest.sh test/test_<your_new_test>.py
```

For example:

```bash
./run_pytest.sh test/test_complete_routing_workflow.py
```

**If the test passes:** You're done! The test is ready to be committed.

**If the test fails:**

- Review the error output
- Fix any issues with locators, timing, or test logic
- Re-run the test until it passes

### Common Systematic Issues from Codegen

These issues will **always** arise from the codegen procedure and must be fixed:

1. **Wrong port number**: Codegen uses hardcoded URLs like `http://localhost:8080/` but tests must:
   - Import `FLASK_PORT` from `cosmonaut_app.config`
   - Use dynamic URLs: `page.goto(f"http://localhost:{FLASK_PORT}/")`
   - Never hardcode port numbers

2. **Missing test fixtures**: Codegen creates tests with:
   ```python
   def test_complete_routing_workflow(playwright: Playwright) -> None:
       browser = playwright.chromium.launch(headless=False)
       context = browser.new_context(viewport={"width": 1280, "height": 720})
       page = context.new_page()
   ```

   This must be changed to use pytest fixtures:
   ```python
   def test_complete_routing_workflow(page, dash_app) -> None:
       # page and dash_app fixtures handle browser/app setup automatically
   ```

   Also remove the cleanup code at the end:
   ```python
   # DELETE these lines:
   page.close()
   context.close()
   browser.close()
   ```

3. **Wrong imports**: Codegen includes unused imports. Remove:
   ```python
   # DELETE these:
   from playwright.sync_api import Playwright, sync_playwright
   ```

   Keep only:
   ```python
   from playwright.sync_api import expect
   ```

4. **File upload locators**: Codegen may use `page.locator("body").set_input_files()` which is too broad. Instead, locate the actual file input:
   ```python
   # For dcc.Upload components, find the input element:
   page.locator(f"#{DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']").set_input_files(
       "test/test_files/memberships.csv"
   )
   ```

5. **Main block**: Codegen adds a `if __name__ == "__main__":` block - delete it entirely:
   ```python
   # DELETE this entire block:
   if __name__ == "__main__":
       with sync_playwright() as playwright:
           test_complete_routing_workflow(playwright)
   ```
