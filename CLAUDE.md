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

# Page-specific input
EMAIL_INPUT_USER_INFO_ID = "email-input-user-info-id"

# Shared/cross-page store
JOB_ID_STORE_SHARED_ID = "job-id-store-shared-id"

# Shared navigation element
SEARCH_INPUT_NAV_SHARED_ID = "search-input-nav-shared-id"

# Map layer (shared across pages)
OSM_GEOJSON_LAYER_MAP_SHARED_ID = "osm-geojson-layer-map-shared-id"

# Config parameter input
CFG_SN_INPUT_ROUTING_PARAMS_ID = "cfg-sn-input-routing-params-id"
```

### File Organization in `html_ids.py`

IDs are organized in a **three-level hierarchy**:

1. **Top Level**: Group by PAGE/SCOPE
   - `SHARED/COMMON` section first (stores, navigation, map elements)
   - Then page-specific sections alphabetically (DATA_UPLOAD, HOME, MAP, etc.)

2. **Second Level**: Group by TYPE within each page
   - Alphabetically: Alerts, Buttons, Divs, Dropdowns, Inputs, etc.

3. **Third Level**: Sort by NAME alphabetically within each type

#### Example Structure:
```python
# ============================================================================
# SHARED/COMMON IDS
# ============================================================================

# --- Stores ---
CLICKED_ROADS_STORE_SHARED_ID = "clicked-roads-store-shared-id"
EMAIL_STORE_SHARED_ID = "email-store-shared-id"
JOB_ID_STORE_SHARED_ID = "job-id-store-shared-id"

# --- Navigation ---
SEARCH_BUTTON_NAV_SHARED_ID = "search-button-nav-shared-id"
URL_DIV_NAV_SHARED_ID = "url-div-nav-shared-id"

# ============================================================================
# PAGE: DATA_UPLOAD
# ============================================================================

# --- Buttons ---
DATA_UPLOAD_NEXT_BUTTON_DATA_UPLOAD_ID = "data-upload-next-button-data-upload-id"
DATA_UPLOAD_PREV_BUTTON_DATA_UPLOAD_ID = "data-upload-prev-button-data-upload-id"

# --- Inputs ---
DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID = "data-upload-epsg-input-data-upload-id"

# ============================================================================
# PAGE: HOME
# ============================================================================

# --- Buttons ---
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"
```

### Usage Guidelines

#### In Layout/Page Files:
```python
from cosmonaut_app.constants.html_ids import *

# Dash components
dbc.Button(
    "Start New Job",
    id=START_JOB_BUTTON_HOME_ID,  # Use constant, not string
    color="primary"
)

dcc.Input(
    id=EMAIL_INPUT_USER_INFO_ID,  # Use constant
    type="email",
    placeholder="Enter email"
)

# HTML components
html.Div(
    id=SELECTION_COUNT_DIV_STREET_SELECTION_ID,  # Use constant
    children="0 roads selected"
)
```

#### In Callback Files:
```python
from cosmonaut_app.constants.html_ids import *

@app.callback(
    Output(EMAIL_INPUT_USER_INFO_ID, "value"),  # Use constant
    Output(USER_INFO_CONTENT_DIV_USER_INFO_ID, "children"),  # Use constant
    Input(USER_INFO_NEXT_BUTTON_USER_INFO_ID, "n_clicks"),  # Use constant
    State(JOB_ID_STORE_SHARED_ID, "data"),  # Use constant for shared elements
    prevent_initial_call=True
)
def handle_user_info_next(n_clicks, job_id):
    # Callback logic...
    pass
```

### Benefits of This Pattern

1. **Type Safety**: IDEs can autocomplete and validate constant names
2. **Refactoring**: Change an ID in one place, updates everywhere
3. **No Typos**: Syntax errors instead of silent runtime failures
4. **Discoverability**: Easy to find all IDs for a page or type
5. **Documentation**: Constant names are self-documenting
6. **Maintainability**: Clear ownership and organization
7. **Search**: Easy to find all usages of an ID across the codebase

### Adding New IDs

When adding a new HTML element that needs an ID:

1. **Define the constant** in `cosmonaut_app/constants/html_ids.py`
   - Find the appropriate page section (or create one)
   - Find the appropriate type subsection (or create one)
   - Add the constant in alphabetical order
   - Follow the naming convention exactly

2. **Use the constant** in your layout/callback
   - Import: `from cosmonaut_app.constants.html_ids import *`
   - Reference the constant, never use a string literal

3. **Update this documentation** if you introduce a new pattern or page

### Common Pitfalls to Avoid

❌ **Don't use string literals:**
```python
# BAD
html.Button(id="start-job", ...)
```

✅ **Always use constants:**
```python
# GOOD
html.Button(id=START_JOB_BUTTON_HOME_ID, ...)
```

❌ **Don't create IDs outside of html_ids.py:**
```python
# BAD - defining constants in page files
HOME_START_BUTTON = "start-button"
html.Button(id=HOME_START_BUTTON, ...)
```

✅ **Always define in html_ids.py:**
```python
# GOOD - html_ids.py
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"

# page file
html.Button(id=START_JOB_BUTTON_HOME_ID, ...)
```

❌ **Don't deviate from naming convention:**
```python
# BAD - doesn't follow <NAME>_<TYPE>_<PAGE>_ID pattern
HOME_START_JOB = "start-job"  # Missing TYPE and ID suffix
BUTTON_START_JOB_ID = "start-job"  # Missing PAGE
```

✅ **Follow the pattern:**
```python
# GOOD
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"
```

---

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
├── app.py             # Main application entry point
├── config.py          # Configuration and environment variables
├── flask_routes.py    # Flask integration and route setup
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

### Git Workflow
- Write clear, descriptive commit messages
- Keep commits focused on single concerns
- Test before committing

### Environment Configuration
- Use `.env` files for configuration (see README.md)
- Never hardcode credentials or secrets
- Use environment-specific files: `env_dev_mock`, `env_test_local`, etc.
- Application reads from `.env`, launcher scripts prepare it

---

## Testing

### Running Tests

**Always run tests before committing changes:**

```bash
./run_pytest.sh
```

This script:
1. Prepares the test environment (copies `env_test_local` to `.env`)
2. Starts required services (PostgreSQL in Docker)
3. Runs all tests with pytest
4. Cleans up (stops Docker containers)

### Test Modes

**Headless Mode (default):**
```bash
./run_pytest.sh
```
- Runs browser tests without visible windows
- Suitable for CI/CD pipelines
- Faster execution

**Headed Mode (visible browser):**
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

### Writing Tests

#### Playwright Tests (for UI/Dash components):
```python
def test_homepage_loads(page, dash_app):
    """Test that the homepage loads without errors."""
    from cosmonaut_app.constants.html_ids import START_JOB_BUTTON_HOME_ID

    page.goto("http://localhost:8050")

    # Use ID constants in selectors
    button = page.locator(f"#{START_JOB_BUTTON_HOME_ID}")
    assert button.is_visible()
```

#### Unit Tests (for logic/utilities):
```python
def test_database_operation():
    """Test database manager functionality."""
    result = DataBaseManager.check_existence("test")
    assert isinstance(result, bool)
```

### Test Requirements

Before committing any changes:
1. ✅ All existing tests must pass
2. ✅ New features should include tests
3. ✅ Bug fixes should include regression tests
4. ✅ Test both happy path and edge cases

### Common Test Issues

**PostgreSQL not starting:**
```bash
# Check Docker is running
docker ps

# Manually start if needed
docker compose up postgres -d
```

**Port conflicts (8050 already in use):**
```bash
# Find and kill process using port 8050
lsof -ti:8050 | xargs kill -9
```

**Stale .env file:**
```bash
# The script handles this, but manual cleanup:
rm .env
./run_pytest.sh
```

### Continuous Integration

In CI/CD pipelines (GitLab CI, GitHub Actions):
- Tests run automatically on push/PR
- Use headless mode (default)
- Playwright browsers are installed via `playwright install --with-deps chromium`
- Environment prepared from `env_test` (not `env_test_local`)

See `.gitlab-ci.yml` for the complete CI testing setup.

---

## Questions or Improvements?

If you're an AI assistant working on this codebase and encounter unclear patterns or have suggestions for improvement, document them in your responses to help future developers and AI assistants working on this project.
