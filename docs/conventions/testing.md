# Testing

All tests live in `test/` and run against real services via Docker.

## Critical Rules for Running Tests

**ALWAYS run `./run_pytest.sh --help` before your first test execution in a session.**
The help output is the single source of truth for available flags and usage. Do not
guess flags or invent arguments — only use what `--help` shows.

**NEVER run `pytest` or `uv run pytest` directly.** Always use `./run_pytest.sh`.
The script manages `.env` backup/restore, Docker services, and cleanup. Running
pytest directly will use the wrong `.env`, skip service setup, and leave stale state.

**`--no-services` SKIPS most tests.** It passes `--no-services` to pytest, which
causes `dash_app` and `celery_worker` fixtures to call `pytest.skip()`. All e2e
tests and most module tests will be skipped. Only use it for tests that truly need
no services (`test_env`, `test_html_id_enforcement`, `test_sensor_routing_descriptions`).

**Check artifacts before rerunning.** On failure, `test/artifacts/<test-name>/`
contains screenshots, traces, HTML snapshots, server logs, and worker logs. Read
these first — they usually explain the failure without needing another run. Note
that `run_pytest.sh` clears previous artifacts by default (use `--keep-artifacts`
to preserve them across runs).

**One test stack per worktree.** Every `run_pytest.sh` run brings up its own stack, so
any number of worktrees (of this repo and of COSMOPOLITAN and cosmo-ecosystem) can run
their suites at the same time. See [below](#one-test-stack-per-worktree).

## One test stack per worktree

- **Compose project from the worktree.** The project is `cosmonaut_test_<hash>`, where
  `<hash>` is the first 8 hex digits of the sha256 of `pwd -P` (the worktree's
  absolute path, since the script runs from the worktree root).
  Containers are `postgres_<project>`, `object_storage_<project>` and
  `redis_<project>`; volumes carry the project prefix. The same worktree always gets
  the same name, so the `down -v` at the start of a run clears what a crashed earlier
  run left there, and the `down -v` at the end removes only this run's stack. Do not
  add `docker stop/rm` by name to the script: on 2026-10-22 that deleted the dev
  containers.
- **Free ports picked at start.** The script asks the OS for five free TCP ports
  (Flask, Postgres, Redis, object storage API and console) and appends them to the
  run's `.env`, both the app-facing variables (`FLASK_PORT`, `POSTGRES_PORT`,
  `REDIS_PORT`, `OBJECT_STORAGE_HOST`) and the published `*_HOST_PORT`. The last
  assignment of a key wins for python-dotenv and compose, so `env_test_local` keeps
  its slot values. The e2e Dash server and the Celery worker read the same `.env`, so
  they use the run's ports too. The suite does not start the tileserver, so it gets no
  port. A port taken between picking and binding fails loudly as "port is already
  allocated"; rerun.
- **Tests must not leave a different `.env` behind.** `test_env.py` rewrites `.env`
  from fixed env files; its `restored_env` fixture puts the run's `.env` and
  `os.environ` back, or later tests and the worker would talk to the slot ports.
- **Finding a running stack.** The run prints `Compose project: …` and the ports at
  start; `docker ps --filter label=com.docker.compose.project=<project>` shows its
  containers.
- **`--no-services`** picks no ports and tears nothing down: it runs against the
  `env_test_local` values, i.e. a stack you started yourself on the cosmonaut slot.

The dev stack (`postgres_cosmonaut` & co.) is a different project and is never stopped
by a test run, and since the test ports are picked free, a running dev stack no longer
gets in the way either. The port slots in
`../cosmo-ecosystem/docs/plan/local-port-allocation.md` apply to dev stacks (and
`--no-services`) only.

`check_parallel_runs.sh` (next to `run_pytest.sh`) is the acceptance check: it creates
a throwaway detached worktree of `HEAD`, runs `run_pytest.sh` on a fast subset that
touches every service (`test_job_deletion`, `test_env`, `test_worker_management`) in
both worktrees at once, and passes when both are green and no container or volume of
either project is left. Run it after changing `run_pytest.sh` (commit first: the probe
worktree sees only `HEAD`). It is not a CI job; CI has no parallel worktrees.

## Code Rules

- All tests go in `test/` (flat directory, no subdirectories)
- Use constants from `cosmonaut_app/constants/html_ids.py` for element IDs in
  Playwright locators — never literal ID strings
- All imports at top level
- When adding a required env var, update `test_env.py`'s checks

## Test Types

### E2E tests (`test_complete_routing_workflow.py`)

- Use Playwright via `pytest-playwright` (`page` fixture)
- App served by `dash_app` fixture (werkzeug make_server in background thread)
- Require all services: Postgres, Redis, object storage, Celery worker
- Test full user workflows through the browser
- Reusable helpers in `test/help_functions_tests.py`

### Module tests (everything else)

Service requirements vary by test:

| Test file | Services needed |
|-----------|----------------|
| `test_db_manager.py` | Postgres |
| `test_maintenance_tasks.py` | Postgres, object storage |
| `test_one_celery_app.py` | Postgres, object storage (imports `app.py`) |
| `test_job_deletion.py` | Postgres, object storage |
| `test_job_run_lifecycle.py` | Postgres, object storage, Redis (cancel and reset revoke) |
| `test_end_mail.py` | Postgres, object storage |
| `test_street_selection_guard.py` | Postgres, object storage |
| `test_worker_management.py` | Redis, Celery worker |
| `test_env.py` | None (reads env files only) |
| `test_html_id_enforcement.py` | None (checks source code only) |
| `test_sensor_routing_descriptions.py` | None (checks data structures only) |

## Fixtures (`conftest.py`)

- `pytest_configure()` verifies all services are reachable before any tests run (gated by `--no-services`)
- `dash_app` (session) — starts the Dash app via werkzeug make_server in a background thread, polls until responsive, shuts down cleanly
- `page` (function) — wraps pytest-playwright's page fixture; captures HTML, console logs, server logs, and worker logs on failure
- `celery_worker` (session) — starts a real Celery worker subprocess with log capture, terminates on teardown. The worker has its own temp `WEB_WORK_DIR`, so web and worker share no disk (ADR 0001, cosmo-ecosystem). The e2e test asserts the finished job's log reaches the page; it goes red if the `pull_file` fallback in `CosmonautJob.get_logs` is removed
- `membership_file_path` / `predictor_file_path` (session) — copies test data files to temp dir
- `logger` — configured logger with suppressed third-party noise

## Artifacts

Playwright artifacts are stored in `test/artifacts/` and include:
- **Screenshots** (`--screenshot only-on-failure`): browser screenshots on test failure
- **Traces** (`--tracing retain-on-failure`): Playwright traces viewable with `npx playwright show-trace`
- **HTML snapshots**: rendered DOM at failure time
- **Console logs**: browser console messages
- **Server logs**: Python server-side logs (callbacks, validation errors, file operations)
- **Worker logs**: Celery worker output

**Which artifact to check first:**

| Failure type | Check first |
|---|---|
| Element not found / timeout | `test-failed-1.png` — is the element on screen? |
| Callback race / stuck overlay | `trace.zip` — step through the action timeline |
| JavaScript error | `console.log` — browser-side errors |
| Unexpected app behavior | `server.log` — Dash callback logs and exceptions |
| Routing task failure | `worker.log` — Celery worker output and task traces |
| Layout / rendering issue | `page.html` — inspect the DOM structure |

## CI Pipeline

Tests run in GitLab CI. See `.gitlab-ci.yml` for configuration.

All tests must pass in CI before merging.

On failure, CI uploads `test/artifacts/` as a GitLab artifact (7-day retention).
Download from the pipeline job page under "Job artifacts".

### CI image (`docker/ci.Dockerfile`)

Test jobs use a pre-built image (`ci:latest`) that bakes in all slow setup:
system dependencies (GDAL, PostgreSQL client, rclone), Python packages, and
Playwright + Chromium. This avoids re-running `apt-get` and `uv sync` on every
pipeline run.

The image lives at:
```
codebase.helmholtz.cloud:5050/ufz/tb5-smm/met/wg7/cosmonaut/ci:latest
```

**When it is rebuilt:** `build-ci-image` runs only when `docker/ci.Dockerfile`,
`pyproject.toml`, or `uv.lock` change (always on main, conditionally on feature
branches). GitLab's own CI registry credentials handle the login — no local
`docker login` is possible or needed (UFZ GitLab uses institutional SSO).
`--build-arg BUILDKIT_INLINE_CACHE=1` embeds layer cache metadata in the pushed
image so future `--cache-from` runs get proper hits on the autoscaler's fresh VMs.

**Dockerfile ENV ordering matters for cache efficiency.** Only set an ENV before
the `RUN` step that actually needs it. Runtime-only ENVs (`TZ`, `UV_NO_SYNC`)
live *after* all expensive `RUN` steps — changing them then only busts the final
cheap ENV layer, not the 60-second apt-get or 70-second playwright layers.

**`UV_NO_SYNC=1` is required in the CI image.** The image is built at `/ci` but
jobs run at `/builds/...`. When the celery worker starts via `uv run celery`,
uv detects the path mismatch and tries to re-sync the venv — adding startup
delay long enough to cause task-timing failures in tests. `UV_NO_SYNC=1` skips
the sync entirely; the pre-built venv is used as-is.

### Two test jobs

| Job | Command | Services | Runs on |
|-----|---------|----------|---------|
| `test-unit` | `pytest --no-services` on 3 files | none | every push |
| `test-integration` | `pytest` (all tests) | Postgres, object storage, Redis | main + MRs only |

`test-unit` and `test-integration` run in parallel when both are active.
The no-service files are: `test_env.py`, `test_html_id_enforcement.py`,
`test_sensor_routing_descriptions.py`. When adding a new test file that needs no
services, add it to the `test-unit` script in `.gitlab-ci.yml`.

**Why `test-integration` is restricted to main and MRs:** the full E2E workflow
includes an OSM road-network download via the Overpass API (`osmnx.graph_from_polygon`)
and a route-computation task. Together these take 8–12 minutes in CI. Running
this on every feature branch push would make CI slower than it was before the
pre-built image existed. Unit tests catch regressions on feature branches;
integration tests gate merges.

**OSM Overpass API timeout.** The street-selection page waits up to 300 seconds
for the Celery worker to complete the OSM download. This is intentionally generous:
the Overpass API can be slow from CI networks, and the task is genuinely
still running (not failed) during that wait. Do not reduce this timeout — a
smaller value causes the test to give up while the worker is still active,
leaving the button disabled and the test failing.

## Examples

### Do

```python
from playwright.sync_api import expect

from cosmonaut_app.constants.html_ids import SOME_BUTTON_ID

def test_something(page, dash_app):
    page.goto(f"http://localhost:{PORT}/")
    page.locator(f"#{SOME_BUTTON_ID}").click()
    expect(page.locator(f"#{SOME_BUTTON_ID}")).to_be_visible()
```

### Don't

```python
def test_something(page, dash_app):
    page.locator("#some_button").click()  # Never use literal ID strings
```

## Notes

- `check_all_errors(page)` in `test/help_functions_tests.py` is the standard post-action verification — checks console errors, JS errors, and broken images
- Use `locator.scroll_into_view_if_needed()` before clicking elements that may be off-screen
