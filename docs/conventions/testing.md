# Testing Conventions

## Testing Approach

Integration testing using Playwright. No unit tests for Dash callbacks.

---

## Local Testing

### `./run_pytest.sh`

Main test runner with automatic service management.

```bash
# Run all tests (headless)
./run_pytest.sh

# Run with visible browser (debugging)
./run_pytest.sh --headed

# Run specific test file
./run_pytest.sh test/test_app.py

# Skip Docker service management
./run_pytest.sh --no-services

# Combine options
./run_pytest.sh --no-services test/test_env.py

# CAUTION these test will not work as they need background services
./run_pytest.sh --no-services test/test_complete_routing_workflow.py
./run_pytest.sh --no-services test/test_db_manager.py
./run_pytest.sh --no-services test/test_worker_management.py
```

**What the script does:**

1. Backs up and replaces `.env` with `env_test_local`
2. Starts Docker services (postgres, minio, redis)
3. Waits for services to be healthy (10 retry limit)
4. Runs pytest with `uv run pytest`
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

## CI Pipeline

Tests run in GitLab CI. See `.gitlab-ci.yml` for configuration.

All tests must pass in CI before merging.

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
- Module-scoped fixtures: `dash_app`, `celery_worker`
- Daemon threads for background services
- Conditional skip with `--no-services` flag
