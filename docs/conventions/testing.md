# Testing Conventions

## Testing Approach

Integration testing using Playwright. No unit tests for Dash callbacks.

---

## Local Testing

### `./run_pytest.sh`

Main test runner with automatic service management.

```bash
# Run all tests (headless) — this is the default and recommended command
./run_pytest.sh

# Run with visible browser (debugging)
./run_pytest.sh --headed

# Run specific test file
./run_pytest.sh test/test_app.py

# Run without artifact capture
./run_pytest.sh --no-artifacts
```

**`--no-services` flag — use with care:**

This flag skips Docker service startup. Only use it when you already have
services running in a separate terminal (see "Development tip" below), or
when running a test that does not require services. Most tests require
PostgreSQL, MinIO, or Redis — running them with `--no-services` and no
background services will produce connection failures, not meaningful results.

```bash
# These tests DO NOT require services:
./run_pytest.sh --no-services test/test_env.py
./run_pytest.sh --no-services test/test_html_id_enforcement.py

# These tests REQUIRE services — they will fail without them:
# test/test_complete_routing_workflow.py
# test/test_db_manager.py
# test/test_worker_management.py
```

**What the script does:**

1. Backs up and replaces `.env` with `env_test_local`
2. Starts Docker services (postgres, minio, redis)
3. Waits for services to be healthy (10 retry limit)
4. Runs pytest with artifact flags (`--screenshot only-on-failure --tracing retain-on-failure --output test/artifacts`)
5. Restores `.env`, stops services

**Service Health Checks:**

- PostgreSQL: `pg_isready`
- MinIO: Health endpoint
- Redis: `ping`

**Development tip:** Keep services running for faster iterations:

```bash
# Terminal 1: Start services once
docker compose up postgres minio redis -d

# Terminal 2: Run tests quickly
./run_pytest.sh --no-services test/test_app.py
```

### `./run_codegen_test.sh`

Generate Playwright tests interactively.

```bash
./run_codegen_test.sh
./run_codegen_test.sh -o test/test_new_feature.py
```

Opens browser, records interactions, outputs test file.

---

## Test Artifacts

On failure, Playwright tests automatically capture artifacts in `test/artifacts/`:

```
test/artifacts/
  test-test-<name>-chromium/
    test-failed-1.png    # Screenshot at moment of failure
    trace.zip            # Playwright trace (DOM, network, actions)
    page.html            # HTML snapshot of the page
    console.log          # Browser console output
    server.log           # Dash/Python server logs during the test
    worker.log           # Celery worker stderr (task execution, errors)
```

**Viewing traces** (the most powerful debugging tool):

```bash
npx playwright show-trace test/artifacts/<test-dir>/trace.zip
```

**Key points:**

- Artifacts are only generated on failure — passing tests produce nothing
- The `test/artifacts/` directory is auto-cleaned at session start by pytest-playwright
- `test/artifacts/` is in `.gitignore`
- `--no-artifacts` flag disables capture (see `./run_pytest.sh --help`)

**Which artifact to check first:**

| Failure type | Check first |
|---|---|
| Element not found / timeout | `test-failed-1.png` — is the element on screen? |
| Callback race / stuck overlay | `trace.zip` — step through the action timeline |
| JavaScript error | `console.log` — browser-side errors |
| Unexpected app behavior | `server.log` — Dash callback logs and exceptions |
| Routing task failure | `worker.log` — Celery worker output and task traces |
| Layout / rendering issue | `page.html` — inspect the DOM structure |

---

## CI Pipeline

Tests run in GitLab CI. See `.gitlab-ci.yml` for configuration.

All tests must pass in CI before merging.

On failure, CI uploads `test/artifacts/` as a GitLab artifact (7-day retention).
Download from the pipeline job page under "Job artifacts".

---

## Test Organization

```
test/
├── test_app.py                         # Dash application tests
├── test_complete_routing_workflow.py   # End-to-end workflow
├── test_db_manager.py                  # Database manager tests
├── test_debug.py                       # DEBUG env tests
├── test_env.py                         # Environment tests
├── test_html_id_enforcement.py         # ID pattern enforcement
├── help_functions_tests.py             # Test helpers
└── test_files/
    └── memberships.csv                 # Sample data
```

---

## conftest.py Patterns

- Custom pytest options via `pytest_addoption()`
- Early validation in `pytest_configure()`
- Session-scoped fixtures: `dash_app`, `celery_worker`
- Daemon threads for background services
- Conditional skip with `--no-services` flag
- `page` fixture override — wraps pytest-playwright's `page` to capture:
  - Browser console messages (via `page.on("console", ...)`)
  - Python/Dash server logs (via `logging.Handler`)
  - HTML snapshot and log files on failure
