# Decision: Adopt cosmo-suite Module by Module, by Measurement Not by Diff Size

**Date:** 2026-08-06
**Status:** Accepted
**Context:** Slice 1 of the `cosmo-suite` integration. The plan listed nine modules
to replace with framework imports, sized by normalized diff lines, on the premise
that the diffs are "~90 % drift — docstrings, trailing commas, placement of classes
— not function". Executing it showed that premise is right for some modules and
wrong for others, and that diff size does not predict which.

## Decision

**A module is adopted only when the framework version is behaviour-equivalent or
better. Where it is not, the local module stays, the divergence is named in its
docstring, and the convergence path is a cosmo-suite MR plus a new tag — never a
local edit of the framework and never a silent regression.**

Concretely, per module:

| Module | Outcome |
|---|---|
| `logs_table.py` | **deleted**, `cosmo_suite.logs_table` |
| `pages/logs.py` | **13-line shim**, `cosmo_suite.pages.logs` (494 → 34, docstring kept) |
| `pages/worker_management.py` | **shim**, `cosmo_suite.pages.worker_management` (871 → 42, docstring kept) |
| `celery_config.py` | **subclasses** `BaseCeleryConfig` (93 → 47) |
| `background_job_manager.py` | **subclasses** framework `BackgroundJobManager` (285 → 111) |
| `logger.py` | **partial** — framework `PostgreSQLHandler`, local filter (288 → 162) |
| `object_storage_manager.py` | **partial** — framework `check_result` + `get_presigned_download_url` (355 → 300) |
| `config.py` | **re-exports** `cosmo_suite.config` (129 → 100) |
| `pydantic_models.py` | **validator only**, not `BaseJobConfig` |
| `files_route.py` | **not adopted** |

### The four cases where the framework version would have been a regression

1. **`object_storage_manager.get_files`.** The framework always downloads with
   `--checksum`, i.e. always overwrites. This app's default is `--ignore-existing`
   so a stale remote copy cannot clobber street-selection edits that have not been
   synced yet (`ff62119`, "Kubernet friendly sync"). The framework also has no
   subprocess timeouts and no connection pre-check, so a hung rclone against an
   unreachable MinIO blocks a worker indefinitely. Adopting the 396-line framework
   module would have looked like the biggest win in the slice and silently undone
   all three.
2. **`BaseCeleryConfig` task time limits.** The framework sets
   `task_soft_time_limit = 3600` / `task_time_limit = 3900`; cosmonaut had none.
   Subclassing inherits them silently. A routing job's runtime scales with survey
   area — sensor-routing is O(n²) and not tileable — so a 65-minute hard kill would
   hit exactly the large surveys the app exists for. Both are overridden to `None`
   with that reason in `celery_config.py`.
3. **`BaseJobConfig`.** Inheriting it adds an `upload_file_name` field. `JobTable`
   has no such column, so `model_dump()` gains a key `CosmonautJob.save()` cannot
   write — measured, not assumed. Cosmonaut has *two* uploads with their own JSON
   columns; the field has no domain meaning. `validate_job_id` is imported from the
   framework and `validate_assignment=True` is adopted separately (it was missing
   entirely — `job.model.job_id = x` bypassed validation until now).
4. **`files_route.py`.** Not drift but a different route set: no
   `/download/<job_id>/route.gpx` (the QR-code and mail target), no `overwrite=True`
   MinIO re-pull, and a picture route resolved against `app.root_path`. Also needs
   the framework `Job`, which is out of slice 1.

### The two silent-failure traps, both real

- **`ObjectStorageError` identity.** The class lives in
  `cosmo_suite.object_storage_manager`, not in `error_handling`. A local class of
  the same name is a *different* class: every `except ObjectStorageError` stops
  catching with no import error and no failing test. `error_handling.py` therefore
  re-exports the framework class (documented convention deviation).
- **`WEB_WORK_DIR`.** `cosmo_suite.config` leaves it relative, as read from the
  env. Flask's `send_from_directory` resolves a relative directory against
  `app.root_path` (= `cosmonaut_app/`), not the CWD, so every job picture would
  404. `cosmonaut_app.config` resolves it with `os.path.abspath` and says why.

## Consequences

- The framework is the source of truth for the names it owns: env vars
  (`POSTGRES_DB`, `FLASK_DEBUG`, python-level `PORT`) and the HTML ids of framework
  pages (`cosmo_suite.constants`). See `docs/conventions/html_ids.md` and
  `docs/conventions/environment_variables.md`.
- Duplication that survives is *documented* duplication. Every partially adopted
  module states what diverges and why in its module docstring, so the next session
  does not re-derive the analysis — or "fix" it by adopting the framework version.
- Four items are queued for a cosmo-suite MR, listed in `docs/project-state.md`:
  object-storage timeout/`check_connection`/`overwrite` parameters, an
  excluded-packages parameter for `ExcludeSubmodulesFilter`, `os.path.abspath` on
  `WEB_WORK_DIR`, and moving `cosmo_suite.layouts`' navbar and reset-modal
  callbacks behind an opt-in registration function instead of registering them at
  import time.
- **Known cost of the two page shims**, measured on a running app in debug mode:
  - Importing a framework page pulls in `cosmo_suite.layouts`, which registers three
    callbacks at import time (one navbar collapse, two reset-modal) whose components
    cosmonaut's `app_layout()` does not mount. Confirmed present in
    `/_dash-dependencies`. They are **inert and silent**: nothing writes to the store
    that triggers them, so they never fire, and Dash reports *no*
    "nonexistent object was used in an Output" — 0 such console messages and 0
    devtools error cards across `/`, `/logs` and `/worker-management`. The cost is
    three dead entries in the callback graph, not user-visible noise. Cleaning it up
    is still the right framework fix (last MR item above), just not urgent.
  - `cosmo_suite.layouts.page_container_column_layout` has no wrapper to carry
    cosmonaut's `.no-map-page` marker class, so both adopted pages first rendered
    squeezed into the content panel beside a map they do not use, with the ag-grid
    column headers truncated to two characters. Fixed app-side in `style.css` by
    also keying the admin-page rules on `#main-content-container`, the id the
    framework helper gives its column. A `className` parameter on that helper is the
    framework-side fix and is on the MR list.
