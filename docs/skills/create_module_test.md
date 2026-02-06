# Skill: Create a New Module Test

Step-by-step checklist for adding an integration test for a core module (database, object storage, config, etc.) — no browser/Playwright involved.

---

## 1. Clarification Questions

Ask the user before starting:

1. **Target module** — Which module or class should be tested? (e.g., `db_manager`, `cosmonaut_job`, `object_storage_manager`)
2. **Services needed** — Does the test require running services (PostgreSQL, MinIO, Redis)?
3. **Scope** — What operations should be tested? (e.g., CRUD, save/load, connectivity)

---

## 2. Step-by-step Checklist

### Step 1: Study existing patterns

Before writing any test code, read:

- `test/test_db_manager.py` — core module test reference
- `test/conftest.py` — available fixtures (`logger`, service health checks)
- The module source under `cosmonaut_app/` — understand the API to test

### Step 2: Create the test file

Create `test/test_<module>.py` following the reference template (see Section 3).

**Key conventions:**

- **Integration tests, not unit tests** — test against real services, no mocking
- **Imports inside test functions** — module-level imports may fail before `.env` is loaded by the test runner; import the module under test inside the function (see `test_db_manager.py` pattern)
- **No Playwright fixtures** — do not use `page`, `dash_app`, or `celery_worker`
- **Use the `logger` fixture** if logging is needed
- **Clean up test data** if the test creates persistent state that could interfere with other tests

### Step 3: Run the test

```bash
# With services (required for most module tests)
./run_pytest.sh test/test_<module>.py

# Without services (only if the test has no service dependencies)
./run_pytest.sh --no-services test/test_<module>.py
```

### Step 4: Verify CI compatibility

- Services (PostgreSQL, MinIO, Redis) are available in CI — no mocking
- `env_test` is used as `.env` in CI (not `env_test_local`)
- Run the full suite to check for regressions:

  ```bash
  ./run_pytest.sh
  ```

---

## 3. Reference Template

```python
"""Test <module> functionality."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_<operation>():
    """Test <what this test validates>."""
    from cosmonaut_app.<module> import <Class>

    # Arrange
    data = {...}

    # Act
    result = <Class>.some_method(data)

    # Assert
    assert result
```

**If the test creates persistent state**, clean up or use unique identifiers:

```python
def test_save_and_load():
    """Test save and load cycle."""
    from cosmonaut_app.cosmonaut_job import CosmonautJob

    job = CosmonautJob()
    job.save()

    loaded = CosmonautJob(job_id=job.model.job_id)
    assert loaded.model.job_id == job.model.job_id
```

---

## 4. Key File References

| File | Purpose |
|------|---------|
| `test/test_<module>.py` | The new test file (create) |
| `test/test_db_manager.py` | Core module test reference (read) |
| `test/conftest.py` | Fixtures and service health checks (read) |
| `cosmonaut_app/<module>.py` | The module being tested (read) |
| `docs/conventions/testing.md` | Testing conventions reference (read) |
| `.gitlab-ci.yml` | CI pipeline configuration (read) |
| `run_pytest.sh` | Local test runner with Docker services |
