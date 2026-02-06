# Skill: Run and Fix Failing Tests

Step-by-step checklist for running tests, diagnosing failures, and fixing issues in the COSMONAUT test suite.

---

## 1. Clarification Questions

Ask the user before starting:

1. **Failure location** — Did the test fail locally, in the CI pipeline, or both?
2. **Test scope** — Which test file is failing, or is it the full suite?
3. **New or regression** — Did this test pass before, or is it newly written?
4. **Error message** — What error are you seeing? (paste the output)

---

## 2. Step-by-step Diagnostic Checklist

### Step 1: Reproduce locally

Always start by running the failing test locally with full services:

```bash
# Run all tests with services (default)
./run_pytest.sh

# Run a specific test file
./run_pytest.sh test/test_<name>.py

# Run with visible browser (Playwright debugging)
./run_pytest.sh --headed test/test_<name>.py
```

**Important:** Always use `./run_pytest.sh` (without `--no-services`) for
verification. See [Testing conventions](../conventions/testing.md).

**Outcome:**

- Passes locally → skip to **Step 5** (CI-specific issues)
- Fails locally → continue to **Step 2**

**Common startup failures:**

| Error | Cause | Fix |
|-------|-------|-----|
| `PostgreSQL not available` | DB container failed health check | `docker logs postgres_cosmonaut` |
| `MinIO not available` | Object storage failed health check | `docker logs minio_cosmonaut` |
| `Redis not available` | Redis failed health check | `docker logs redis_cosmonaut` |
| Port already in use | Another process on 5433/9010/6380 | Stop conflicting service or check `env_test_local` |
| Docker not running | Docker daemon not started | `sudo systemctl start docker` |

---

### Step 2: Does the test need services?

Check the test function signature for fixture dependencies:

- Has `dash_app` or `celery_worker` parameter → **requires services**
- No service fixtures → can run with `--no-services`

| Requires services | No services needed |
|---|---|
| `test_complete_routing_workflow.py` | `test_env.py` |
| `test_db_manager.py` | `test_html_id_enforcement.py` |
| `test_worker_management.py` | |

Running a service-dependent test with `--no-services` produces connection
failures, not meaningful results. If unsure, run with services.

---

### Step 3: Check if test is flaky

**Symptoms:**

- Test passes sometimes, fails other times
- Timeout errors on `expect().to_be_visible()`
- Different behavior with `--headed` vs headless

**Diagnostic — run 3-5 times:**

```bash
for i in {1..5}; do
    echo "--- Run $i ---"
    ./run_pytest.sh test/test_<name>.py || break
done
```

**Run with visible browser to observe timing:**

```bash
./run_pytest.sh --headed test/test_<name>.py
```

**Common timing fixes:**

| Issue | Fix |
|-------|-----|
| Element not rendered yet | Add `expect(page.locator(f"#{ID}")).to_be_visible()` before interaction |
| Background job not complete | Increase timeout: `expect(...).to_be_enabled(timeout=120000)` |
| Callback race condition | Add `check_all_errors(page)` after navigation |
| Upload not processed | Wait for upload confirmation before next action |

---

### Step 4: Check service health

If tests require services and startup errors occur, verify each service manually.

**PostgreSQL:**

```bash
docker ps | grep postgres_cosmonaut
docker logs postgres_cosmonaut
docker exec postgres_cosmonaut pg_isready -U cosmonaut
```

**MinIO:**

```bash
docker ps | grep minio_cosmonaut
docker logs minio_cosmonaut
curl -sf http://localhost:9010/minio/health/ready
```

**Redis:**

```bash
docker ps | grep redis_cosmonaut
docker logs redis_cosmonaut
docker exec redis_cosmonaut redis-cli ping
```

**Clean up and restart:**

```bash
docker compose down
./run_pytest.sh
```

If lingering containers cause port conflicts:

```bash
docker ps -a | grep cosmonaut
docker compose down --remove-orphans
```

---

### Step 5: CI pipeline issues (passes locally, fails in CI)

**Environment differences:**

| Aspect | Local (`env_test_local`) | CI (`env_test`) |
|--------|--------------------------|------------------|
| PostgreSQL | `localhost:5433` | `postgres:5432` |
| MinIO | `localhost:9010` | `minio:9000` |
| Redis | `localhost:6380` | `redis:6379` |
| Browser | `--headed` option available | headless only |
| Services | Docker Compose containers | GitLab service containers |

**Common CI-specific failures:**

1. **Hardcoded hostnames or ports** — use config vars from `cosmonaut_app/config.py`, never literals
2. **Hardcoded absolute file paths** — use paths relative to project root (e.g. `test/test_files/data.csv`)
3. **Test assumes visible browser** — remove any `headless=False`; use fixtures, not manual browser setup
4. **Missing test files** — check that files are committed and not in `.gitignore`

**Compare environment files:**

```bash
diff env_test env_test_local
```

**Check CI pipeline configuration:** `.gitlab-ci.yml`

---

### Step 6: Common failure patterns

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `PostgreSQL not available` | DB container not healthy | Check Docker logs, verify ports in `env_test_local` |
| `locator.click: Timeout 30000ms exceeded` | Element not visible or not rendered | Add `expect().to_be_visible()` before interaction |
| `VIOLATIONS: Found id= usages with string literals` | Literal ID strings in page code | Replace with constants from `cosmonaut_app/constants/html_ids.py` |
| `ModuleNotFoundError` | Missing dependency or inline import | Run `uv sync`; move import to top level |
| `AssertionError` | Test expectation does not match behavior | Verify whether test or code is wrong |
| `Celery worker failed to start` | Redis broker issue or import error | Check Redis is running; check worker imports |
| Passes locally, fails CI | Environment differences | Check config vars vs hardcoded values; compare `env_test` and `env_test_local` |
| Random pass/fail (flaky) | Race condition, insufficient waits | Add explicit waits with appropriate timeouts |

---

### Step 7: Fix and verify

1. **Make the fix**
2. **Run the specific failing test:**
   ```bash
   ./run_pytest.sh test/test_<name>.py
   ```
3. **Run the full test suite:**
   ```bash
   ./run_pytest.sh
   ```
4. **If timing-related, check for flakiness** (run 3-5 times)
5. **Push and verify CI pipeline passes**

---

## 3. Decision Tree

```
Test failure
│
├── Does it fail locally? (./run_pytest.sh test/test_<name>.py)
│   ├── No → Step 5: CI-specific issues
│   └── Yes ↓
│
├── Does the test need services? (check fixtures)
│   ├── No → run with --no-services, check test logic
│   └── Yes ↓
│
├── Are services healthy? (Step 4: docker logs, health checks)
│   ├── No → fix service startup, clean up containers
│   └── Yes ↓
│
├── Is it flaky? (run 3-5 times)
│   ├── Yes → Step 3: fix timing/waits
│   └── No ↓
│
├── What type of error?
│   ├── locator not found → check HTML IDs, add waits
│   ├── timeout → increase timeout, check for JS errors
│   ├── assertion failed → verify test expectations vs actual behavior
│   ├── import error → uv sync, check top-level imports
│   ├── ID enforcement violation → use constants from html_ids.py
│   └── other → check logs, run with --headed
│
└── Fix → verify specific test → verify full suite → verify CI
```

---

## 4. Key File References

| File | Purpose |
|------|---------|
| `./run_pytest.sh` | Main test runner with service management |
| `test/conftest.py` | Fixtures (`dash_app`, `celery_worker`), health checks |
| `test/help_functions_tests.py` | `check_all_errors(page)` utility |
| `env_test_local` | Local test environment (custom ports) |
| `env_test` | CI test environment (service hostnames) |
| `.gitlab-ci.yml` | CI pipeline configuration |
| `cosmonaut_app/constants/html_ids.py` | HTML ID constants for Playwright locators |
| `docs/conventions/testing.md` | Testing conventions reference |
