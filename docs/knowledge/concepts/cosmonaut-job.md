# CosmonautJob

`CosmonautJob` ([cosmonaut_app/cosmonaut_job.py](../../../cosmonaut_app/cosmonaut_job.py)) is the
spine of the application: it represents one user submission and owns **all** of its state. Every
page and every Celery task loads a job, mutates it, and saves it. Understanding how it persists
state — and the sync rules that differ between the web pod and the worker pod — is essential to
working on COSMONAUT without corrupting jobs.

## Two-tier persistence

A job's state is split across two stores, and `CosmonautJob` is the only thing that keeps them
coherent:

1. **Business data → PostgreSQL.** Held in `self.model`, a `JobModel` Pydantic instance
   ([pydantic_models.py](../../../cosmonaut_app/pydantic_models.py)). On `save()`, the model is
   dumped to JSON and **split**: every field that belongs to sensor-routing's `FullPipelineConfig`
   goes into a single JSONB `config` column; the remaining `JobModel` fields (`job_id`, `status`,
   `stage`, `email`, `submitted`, `celery_task_id`, `start_date`, the `*_upload` dicts, …) become
   ordinary columns. `load()` reverses this — it pops `config` and merges it back so `self.model`
   is whole again. The split is driven dynamically by `FullPipelineConfig.model_fields`, so adding a
   routing parameter on the sensor-routing side needs no schema change here.
2. **Files → object storage.** Each job has a `working_dir` at `WEB_WORK_DIR/<job_id>` holding the uploaded
   CSVs, the OSM GeoJSON files, `parameters.json`, logs, the route solution, GPX and QR code. `save()`
   uploads this directory to object storage via rclone; `job_persistence.work_dir(job_id)` brings it back.

## Persistence calls — what costs rclone

Persistence is the framework's `cosmo_ecosystem.job_persistence` (remote prefix authoritative, work dir a
cache; see the framework's ADR 0001). `CosmonautJob` only maps its model to a row dict:

- **`CosmonautJob(job_id)`** reads the row only: no rclone. Polls and Dash callbacks use it as is.
- **`job_persistence.work_dir(job.job_id)`** makes the work dir current with object storage (`rclone
  --checksum`, never deletes local files); `job.working_dir` is only the path (`local_dir`). Call it where
  files are read: worker tasks, the Route & Download page, the file routes.
- **`job_persistence.pull_file(job_id, name)`** pulls one file (two rclone subprocesses): the GPX route
  and the map callbacks.
- **`job.update_columns("stage", ...)`** writes named model fields to the row. No storage access. Status
  and stage bumps use it.
- **`job.save()`** uploads the work dir, then writes the whole row. Input changes (uploads, route
  direction) use it so no edit exists only on local disk. **Pull before you write and save**
  (`upload_membership`, `upload_predictor` and `submit` do it themselves): the upload is `rclone copy
  --checksum`, so an outdated local file would replace the newer stored one.
- **Deleting a job file** goes through `job_persistence.delete_files`, which removes it locally and
  remotely at once; a later upload deletes nothing remote.

## Stage, status, and the two progress trackers

- `model.status` is the coarse lifecycle enum — `PENDING` / `RUNNING` / `COMPLETED` / `FAILED`
  (constants in [constants/general.py](../../../cosmonaut_app/constants/general.py)). It tracks the
  **routing** job.
- `model.stage` is an integer high-water mark (0–4) set as the user advances through the workflow
  pages. `get_completed_steps()` maps it to the step list shown in the UI (`stage >= 1` → user_info
  done, `>= 2` → data_upload, `>= 3` → street_selection, `>= 4` → routing_params;
  `status == COMPLETED` → route_computation).
- **`membership_upload["street_processing"]` is overloaded on purpose:** it holds either a status
  string (`"PENDING"` / `"COMPLETED"` / `"FAILED"`) **or** a live Celery task ID. `get_street_processing_status()`
  branches on this — if the value isn't one of the three known strings it treats it as a task ID and
  queries Celery, promoting it to a real status (and bumping `stage`) once the task terminates. The
  same pattern drives `get_status()`, which lazily syncs `RUNNING` → `COMPLETED`/`FAILED` from Celery.

## Lifecycle methods

`submit()` flips `status` to `RUNNING`, saves (so the worker can pull a clean copy), and enqueues the
routing task. `reset()` cancels a running task, deletes **output** files (logs, solution, GPX, QR) but
**preserves inputs** (uploaded data, parameters, OSM data), and returns the job to `PENDING`.
`delete_membership()` cascades — it revokes any in-flight upload task, deletes the predictor, the OSM
files and plots, and resets `membership_upload`. `time_to_live()` computes days-until-cleanup from
`start_date` and the submitted/not-submitted retention windows.

## Do / Don't

- **Do** call `job_persistence.work_dir(job.job_id)` in Celery tasks and where a page or route reads job files.
- **Do** use `update_columns` for status and stage changes; `save()` is for file changes.
- **Don't** assume `street_processing` is a status string — it may be a Celery task ID.
- **Don't** add a field to `JobModel` expecting it in the `config` JSONB (or vice-versa): the split
  is by membership in `FullPipelineConfig.model_fields`, not by where you declare it.
- **Don't** write to `working_dir` and forget to `save()` — files not uploaded never reach object storage and
  are lost when the stateless web pod restarts. Street edits are the sanctioned exception: their intent
  is in the `street_edits` column and the edited/projected GeoJSON are derived files that `StreetSelector`
  recomputes when missing or stale (see `street_selector.py`).

## Related links

- Code: [cosmonaut_job.py](../../../cosmonaut_app/cosmonaut_job.py),
  [pydantic_models.py](../../../cosmonaut_app/pydantic_models.py),
  [db_manager.py](../../../cosmonaut_app/db_manager.py),
  [object_storage_manager.py](../../../cosmonaut_app/object_storage_manager.py)
- Systems: [background-tasks](../systems/background-tasks.md) (how `submit()` and the status sync
  reach Celery), [sensor-routing-integration](../systems/sensor-routing-integration.md) (where the
  `config` JSONB fields come from), [osm-backend](../systems/osm-backend.md) (the OSM files in
  `working_dir`)
- Overview: [architecture.md](../../architecture.md)
