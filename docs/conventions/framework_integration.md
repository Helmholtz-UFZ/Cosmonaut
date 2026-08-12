# Framework Integration (`cosmo-suite`)

COSMONAUT shares its infrastructure — Dash shell, Celery, Postgres, MinIO — with
COSMOPOLITAN through the **`cosmo-suite`** package. This file is about working with
that dependency. What each adopted module does is documented in its own docstring;
what was decided and why is in `docs/decisions/`.

---

## The three standing rules

### 1. Freeze rule — work against a tag, never patch the installed package

`pyproject.toml` pins an exact framework tag:

```toml
"cosmo-suite @ git+https://codebase.helmholtz.cloud/ufz/tb5-smm/met/wg7/cosmo-suite@v0.4.0",
```

If the framework needs to change, the change is an **MR in the framework repo plus a
new tag**, then both apps re-pin. Never edit `site-packages`, never carry a local
patch. COSMOPOLITAN integrates against the same tag in parallel; a local patch is
invisible to it and to CI.

Two things the pin needs on the app side, both easy to lose:

- `[tool.hatch.metadata] allow-direct-references = true` — hatchling refuses a direct
  git reference otherwise, and the editable install of the app itself fails to build.
- **`git` in `docker/ci.Dockerfile`.** The CI image installs from
  `uv export --format requirements-txt`, which emits the dependency as a
  `git+https://…` URL. Without the git binary the image build breaks on the next
  `uv.lock` change — not on the change that introduced it.

### 2. CWD rule — every entry point starts from the repo root

`cosmo_suite.config` loads the environment with
`load_dotenv(find_dotenv(usecwd=True))`. It searches upward from the **process CWD**,
not from next to `config.py`, which lives in `site-packages`.

So `dev_up.sh`, `run_pytest.sh`, gunicorn, the Celery worker and the deployment
manifests must all start from the repo root. The three images already do
(`WORKDIR /python_docker/cosmonaut`, `.env` in it). A new entry point that does not
gets an empty environment and a `ValueError` from the first `getenv()`.

### 3. Adoption rule — adopt by behaviour, not by diff size

> Adopt the framework version only where it is behaviour-equivalent or better.
> Where it is not, the local module stays, **the divergence is named in its
> docstring**, and a framework MR is queued. **Diff size does not predict which case
> you are in.**

This is the most expensive lesson of slice 1. Modules that looked like pure drift
(trailing commas, docstrings, class placement) carried load-bearing behaviour, and a
wholesale swap would have been a silent regression in four places — including a
`get_files` default that would have clobbered unsynced street-selection edits, and a
framework task time limit that would have killed exactly the large surveys the app
exists for. See
[decisions/20260806-cosmo-suite-slice1-adopt-by-measurement.md](../decisions/20260806-cosmo-suite-slice1-adopt-by-measurement.md).

The corollary matters as much: **a workaround that stays local hits the next
consumer.** Every divergence found in slice 1 went into the framework in `v0.4.0`,
which is why slice 1b could delete the local modules outright instead of maintaining
them forever.

---

## Two silent traps

Both fail with **no import error and no failing test**. Neither is hypothetical —
both were found by reading the code, not by a red test.

### `ObjectStorageError` must be re-exported, never redefined

The class lives in `cosmo_suite.object_storage_manager`. A local class of the same
name in `error_handling.py` is a **different class**: every
`except ObjectStorageError` silently stops catching and the exception falls through
to the generic handler. `cosmonaut_app/error_handling.py` therefore imports it (a
documented deviation from "custom exceptions live in error_handling.py").

The same shape applies to any framework exception the app catches. If you find
yourself writing `class SomethingError(Exception)` and the framework raises a
`SomethingError` too, you have this bug.

### `WEB_WORK_DIR` must be absolute

Flask's `send_from_directory` resolves a *relative* directory against
`app.root_path` — the installed app package — not the CWD. The `.env` files ship
`"./cosmonaut_app/work_dir"`, so an unresolved value means **every job file 404s**
while nothing logs an error. `cosmo_suite.config` resolves it with `os.path.abspath`
since `v0.4.0`; before that the app did it locally.

**When touching this: click a job picture.** No test covers it.

---

## Local port allocation

The three stacks — cosmopolitan, cosmonaut, `cosmo-suite/examples/csv_profiler` —
used to publish the same host ports, so **no two suites could run at once, in any
combination**. Each repo now owns a disjoint block:

| | Flask | Postgres | Redis | MinIO | Console | Tileserver |
|---|---|---|---|---|---|---|
| cosmopolitan | 8080 | 5432 | 6379 | 9000 | 9001 | 8001 |
| **cosmonaut** | **8081** | **5433** | **6380** | **9010** | **9011** | **8011** |
| csv_profiler | 8082 | 5434 | 6381 | 9020 | 9021 | — |

**Canonical source:** `../cosmo-suite/docs/plan/local-port-allocation.md`. Do not
invent an allocation here — a second table is how the collision comes back, harder
to find. Extend that one.

Only `env_dev_mock` and `env_test_local` carry these values. `env_prod`,
`env_dev_prod*`, `env_test` and the k8s manifests are untouched and must stay that
way: in CI every stack has its own containers, in production its own pod. The one
host-published literal in `docker-compose.yml` is parametrised as
`${TILESERVER_HOST_PORT:-8001}` — **with the variable unset the resolved
`docker compose config` is byte-identical to before**, which is what keeps prod out
of it. Postgres, Redis and MinIO already published through a variable with the
container side fixed (`${POSTGRES_PORT}:5432`), which is the shape that works;
`FLASK_PORT` needs no host variable because the app and worker run with
`network_mode: host`.

### A port collision does not look like a failure

It looks like **setup ERRORs** ("Address already in use" from
`werkzeug.serving`) or like e2e tests running against no server — i.e. like a bug
somewhere else entirely. Two runs were lost to this before the allocation existed.

The inverse also happens: three setup ERRORs that look exactly like a collision but
are a missing Playwright browser build after a version bump
(`BrowserType.launch: Executable doesn't exist at …/chromium_headless_shell-<n>`).
Fix with `uv run playwright install chromium`. **Read the error before blaming the
ports.**

---

## Who owns what

- **Env-var names**: the framework owns the service-level half. It reads
  `POSTGRES_DB` and `FLASK_DEBUG` (not `POSTGRES_NAME` / `DEBUG`) and exports the
  derived python names `DEBUG` and `PORT`. Details and the full list:
  [environment_variables.md](environment_variables.md).
- **HTML ids**: whoever renders the component owns its id — framework pages take
  theirs from `cosmo_suite.constants`, and so do the tests that locate them. Details:
  [html_ids.md](html_ids.md).
- **User-facing page prose**: the app owns it. The two framework pages are thin
  shims under `cosmonaut_app/pages/` whose only job is to be imported by Dash's page
  discovery (`register_page` must run after `Dash(...)`) and to carry the docstring
  that `doc_generator` parses. The implementation lives in `cosmo_suite.pages.*`.

---

## Known open items

Tracked in `docs/project-state.md`; kept here only as a pointer, so this file does
not drift into a second changelog:

- `cosmo_suite.pages.*` do not pass `wrapper_class` through to
  `page_container_column_layout`, so the app still keys its admin-page CSS on
  `#main-content-container` (see the comment in `assets/style.css`).
- `cosmo_suite.layouts.toggle_navbar_collapse` is still registered at module import,
  so importing a framework page adds one callback whose component this app does not
  mount. Inert — it never fires — but it belongs behind the same opt-in as the reset
  callbacks.
- `files_route.py` and `error_handling.py` wait on framework seams that do not exist
  yet (a registrable domain file route; an `on_unhandled` hook, without which the
  maintainer mails would be lost silently).
- Two SQLAlchemy engines run in the process until slice 2:
  [decisions/20260806-two-sqlalchemy-engines-transitional.md](../decisions/20260806-two-sqlalchemy-engines-transitional.md).
