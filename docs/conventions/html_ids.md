# HTML ID Conventions

## When to Create IDs

**ONLY create IDs when necessary.** Valid use cases:

1. **Callbacks** - Components used in `Input()`, `Output()`, or `State()`
2. **Tests** - Components that need Playwright locators
3. **set_props()** - Components updated via `set_props()` (requires `# nocheck`)
4. **Dynamic construction** - Programmatically constructed IDs (requires `# nocheck`)

**NEVER use literal ID strings** - always use constants or construct programmatically.

---

## Naming Convention

**Format:** `<NAME>_<TYPE>_<PAGE>_ID`

### Components

1. **NAME** - Semantic purpose
   - Examples: `START_JOB`, `EMAIL`, `SEARCH`, `TAGS`
   - Descriptive, action-oriented
   - Avoid abbreviations

2. **TYPE** - Element/component type
   - `BUTTON`, `INPUT`, `DIV`, `DROPDOWN`, `STORE`, `MODAL`, `ALERT`, `LINK`, `LAYER`
   - Use Dash/HTML component type names

3. **PAGE** - Page name or scope
   - Page names: `HOME`, `USER_INFO`, `DATA_UPLOAD`, `STREET_SELECTION`, `ROUTING_PARAMS`
   - Cross-page: `SHARED` or `COMMON`

4. **ID** - Required suffix

### HTML Value Format

Constants map to **kebab-case** HTML values:

```python
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"
```

**Exception — dict-style callbacks:** When an ID is used as a key in dict-style
`@callback(output={...}, inputs={...})` patterns, Dash requires keys to be valid
Python identifiers. These IDs must use **underscores** instead of hyphens:

```python
CHECK_INPUT_BUTTON_INPUT_ID = "check_input_button_input_id"  # underscores required
```

---

## File Organization

IDs in `cosmonaut_app/constants/html_ids.py` use three-level hierarchy:

1. **Top level** - Group by PAGE/SCOPE
   - `SHARED/COMMON` section first
   - Page-specific sections alphabetically

2. **Second level** - Group by TYPE within each page
   - Alphabetically: Alerts, Buttons, Divs, Dropdowns...

3. **Third level** - Sort by NAME alphabetically

---

## `# nocheck` Comment

Mark IDs with `# nocheck` when:
- Used with `set_props()` (not standard callbacks)
- Dynamically constructed IDs
- Used exclusively for testing/automation

Example:
```python
ERROR_MODAL_MESSAGE_SHARED_ID = "error-message"  # nocheck
```

---

## Enforcement

Test validates ID usage: `test/test_html_id_enforcement.py`

Run: `cd test && uv run pytest test_html_id_enforcement.py -v --noconftest`

Checks:
1. All `id=` usages use constants (no string literals)
2. All constants are used in callbacks (or marked `# nocheck`)
