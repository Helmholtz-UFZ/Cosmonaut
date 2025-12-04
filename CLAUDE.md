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
├── constants/          # Application constants
│   ├── __init__.py
│   └── html_ids.py    # HTML element ID constants
├── pages/             # Page layouts AND callbacks (one file per page)
│   ├── data_upload.py      # Data upload page + 11 callbacks
│   ├── home.py             # Home page + 1 callback
│   ├── route_download.py   # Route download page + 1 callback
│   ├── routing_params.py   # Routing parameters page + 3 callbacks
│   ├── street_selection.py # Street selection page + 12 callbacks
│   └── user_info.py        # User info page + 3 callbacks
├── app.py             # Main application: Flask/Dash setup and entry point
├── config.py          # Configuration and environment variables
└── layout.py          # Shared layout components + shared callbacks (6 callbacks)
```

### Key Architectural Principles

1. **Colocated Layouts and Callbacks**:

   - Each page file contains both layout definition and page-specific callbacks
   - Shared callbacks (navbar, map interactions) are in `layout.py`
   - Constants in `constants/`
   - Configuration in `config.py`

2. **Callback Organization**:

   - **Page-specific callbacks**: Placed at the bottom of their page file (e.g., `pages/user_info.py` contains email validation callbacks)
   - **Shared callbacks**: Placed at the bottom of `layout.py` (e.g., navbar search, map updates, email store)
   - Standard structure: Layout definition → Helper functions → Callbacks section
   - Page callbacks use `@callback` decorator (auto-registered via Dash pages plugin)
   - Shared callbacks use `@app.callback` decorator (registered when layout.py is imported in app.py)

3. **Page Independence**:
   - Each page is self-contained with its layout and callbacks
   - Pages don't directly import from each other
   - Shared elements use `SHARED` or `COMMON` naming
   - Pages auto-register via `use_pages=True` in app.py

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

The project uses `run_pytest.sh` for running tests with automatic service management.

**Basic Usage:**

```bash
# Run all tests (headless, default for CI)
./run_pytest.sh

# Run all tests with visible browser (for debugging)
./run_pytest.sh --headed

# Run specific test file
./run_pytest.sh test/test_app.py

# Skip Docker service management (assumes services already running)
./run_pytest.sh --no-services

# Combine options (except --headed and test path are mutually exclusive)
./run_pytest.sh --no-services test/test_complete_routing_workflow.py
```

**What the script does:**

1. Backs up and replaces `.env` with `env_test_local`
2. Starts Docker services (postgres, minio, redis) unless `--no-services` is used
3. Waits for all services to be healthy (10 retry limit)
4. Runs pytest with `uv run pytest`
5. Cleans up: restores `.env`, stops services

**Service Health Checks:**

- PostgreSQL: `pg_isready` check
- MinIO: Health endpoint check
- Redis: `ping` command check

**Options:**

- `--headed`: Run Playwright tests with visible browser (all tests)
- `--no-services`: Skip Docker service management
- `[TEST_PATH]`: Run specific test file/directory (mutually exclusive with `--headed`)
- `-h, --help`: Show help message

**Development Tip:** If you're running multiple test iterations, keep services running and use `--no-services` to speed up test execution:

```bash
# Terminal 1: Start services once
docker compose up postgres minio redis -d

# Terminal 2: Run tests quickly without service restarts
./run_pytest.sh --no-services test/test_app.py
```

### Test Organization

```
test/
├── test_app.py                         # Dash application tests (Playwright)
├── test_complete_routing_workflow.py   # End-to-end routing workflow test
├── test_db_manager.py                  # Database manager tests
├── test_debug.py                       # DEBUG environment variable tests
├── test_env.py                         # Environment configuration tests
├── test_html_id_enforcement.py         # HTML ID pattern enforcement
├── help_functions_tests.py             # Test helper functions
└── test_files/                         # Test data files
    └── memberships.csv                 # Sample CSV for upload tests
```

## Questions or Improvements?

If you're an AI assistant working on this codebase and encounter unclear patterns or have suggestions for improvement, document them in your responses to help future developers and AI assistants working on this project.
