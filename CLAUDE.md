# COSMONAUT Development Guidelines for AI Assistants

This document provides guidelines and design patterns for AI assistants (like Claude) working on the COSMONAUT codebase.

## Table of Contents

- [HTML ID Design Pattern](#html-id-design-pattern)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing](#testing)

---

## HTML ID Design Pattern

### Overview

All HTML element IDs in the COSMONAUT Dash application **must be defined as constants** in `cosmonaut_app/constants/html_ids.py`. This ensures consistency, prevents typos, enables IDE autocomplete, and makes refactoring safer.

**This design pattern is enforced by automated tests** in `test/test_html_id_enforcement.py`. The test checks:
1. All `id=` usages in Dash components use constants from `html_ids.py` (no string literals allowed)
2. All constants in `html_ids.py` are used in `@app.callback` decorators (or marked with `# nocheck` comment)

Run the enforcement test: `cd test && uv run pytest test_html_id_enforcement.py -v --noconftest`

### Naming Convention

**Format**: `<NAME>_<TYPE>_<PAGE>_ID`

#### Components:

1. **NAME**: Semantic name describing the element's purpose

   - Examples: `START_JOB`, `EMAIL`, `SEARCH`, `TAGS`, `ROUTE`
   - Use descriptive, action-oriented names
   - Avoid abbreviations unless universally understood

2. **TYPE**: Element type or component class

   - Common types: `BUTTON`, `INPUT`, `DIV`, `DROPDOWN`, `STORE`, `MODAL`, `ALERT`, `LINK`, `IMAGE`, `LAYER`
   - Use Dash/HTML component type names
   - Be specific: `DROPDOWN` for dcc.Dropdown, `STORE` for dcc.Store

3. **PAGE**: Page name or scope

   - Use actual page names: `HOME`, `USER_INFO`, `DATA_UPLOAD`, `STREET_SELECTION`, `ROUTING_PARAMS`, `ROUTE_DOWNLOAD`, `MAP`
   - For cross-page elements, use: `SHARED` or `COMMON`
   - Use underscores for multi-word pages: `USER_INFO`, `DATA_UPLOAD`

4. **ID**: Suffix for all ID constants (mandatory)

#### HTML Value Format:

- Constants map to **kebab-case** HTML ID values
- Example: `START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"`
- The constant name is uppercase with underscores; the HTML value is lowercase with hyphens

### Examples

```python
# Page-specific button
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"

# Shared navigation element
SEARCH_INPUT_NAV_SHARED_ID = "search-input-nav-shared-id"
```

### File Organization in `html_ids.py`

IDs are organized in a **three-level hierarchy**:

1. **Top Level**: Group by PAGE/SCOPE

   - `SHARED/COMMON` section first (stores, navigation, map elements)
   - Then page-specific sections alphabetically (DATA_UPLOAD, HOME, MAP, etc.)

2. **Second Level**: Group by TYPE within each page

   - Alphabetically: Alerts, Buttons, Divs, Dropdowns, Inputs, etc.

3. **Third Level**: Sort by NAME alphabetically within each type

## Project Structure

### Directory Layout

```
cosmonaut_app/
├── callbacks/          # Callback functions (separated by concern)
│   ├── callbacks_job.py
│   ├── callbacks_map.py
│   ├── callbacks_routing_params.py
│   ├── callbacks_routing.py
│   ├── callbacks_ui.py
│   ├── callbacks_upload.py
│   └── callbacks_user_info.py
├── constants/          # Application constants
│   ├── __init__.py
│   └── html_ids.py    # HTML element ID constants
├── pages/             # Page layouts (one file per page)
│   ├── data_upload.py
│   ├── home.py
│   ├── map.py
│   ├── route_download.py
│   ├── routing_params.py
│   ├── street_selection.py
│   └── user_info.py
├── app.py             # Main application: Flask/Dash setup, layout, and entry point
├── config.py          # Configuration and environment variables
└── layout.py          # Shared layout components
```

### Key Architectural Principles

1. **Separation of Concerns**:

   - Layouts in `pages/`
   - Callbacks in `callbacks/`
   - Constants in `constants/`
   - Configuration in `config.py`

2. **Callback Organization**:

   - Group by functional area (job management, map, routing, UI, upload, user info)
   - Each callback file focuses on one concern
   - Callbacks reference page elements via ID constants

3. **Page Independence**:
   - Each page is self-contained in its layout definition
   - Pages don't directly import from each other
   - Shared elements use `SHARED` or `COMMON` naming

---

## Coding Standards

### Python Style

- Follow PEP 8 for Python code style
- Use type hints where beneficial
- Document complex logic with comments
- Keep functions focused and single-purpose

### Dash/React Patterns

- Use descriptive component IDs (via constants)
- Minimize callback complexity
- Use `prevent_initial_call=True` when appropriate
- Handle edge cases in callbacks (None values, empty lists, etc.)

### Environment Configuration

- Use `.env` files for configuration (see README.md)
- Never hardcode credentials or secrets
- Use environment-specific files: `env_dev_mock`, `env_test_local`, etc.
- Application reads from `.env`, launcher scripts prepare it

---

## Testing

### Running Tests

Check regularly that your development process run well with:

```bash
./run_pytest.sh
```

For human devs you can use:

```bash
./run_pytest.sh --headed
```

- Shows browser window during tests
- Useful for debugging test failures
- Allows visual inspection of UI behavior

### Test Organization

```
test/
├── test_app.py          # Dash application tests (Playwright)
├── test_db_manager.py   # Database manager tests
├── test_debug.py        # DEBUG environment variable tests
└── test_env.py          # Environment configuration tests
```

## Questions or Improvements?

If you're an AI assistant working on this codebase and encounter unclear patterns or have suggestions for improvement, document them in your responses to help future developers and AI assistants working on this project.
