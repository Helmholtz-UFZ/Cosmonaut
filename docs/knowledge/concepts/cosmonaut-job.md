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
2. **Files → MinIO.** Each job has a `working_dir` at `WEB_WORK_DIR/<job_id>` holding the uploaded
   CSVs, the OSM GeoJSON files, `parameters.json`, logs, the route solution, GPX and QR code. `save()`
   syncs this directory to MinIO via rclone (`save_files`); `load()` pulls it back (`get_files`).

## `sync_files` and `overwrite` — the web-vs-worker footgun

Both `__init__`/`load` and `save` take keyword-only flags that control the (slow) rclone round-trip.
Getting these wrong either loses recent edits or wastes seconds per callback:

- **`sync_files=False` on load** (Dash callbacks, web pod): local files are already current, so skip
  the download. Pulling from MinIO here would be slow *and* could overwrite recent local edits with
  stale remote files.
- **`overwrite=True` on load** (worker pods): force a clean copy from MinIO (`rclone --checksum`).
  The worker starts cold and must get exactly what the web pod last saved — e.g.
  `CosmonautJob(job_id=job_id, overwrite=True)` in both [routing_tasks.py](../../../cosmonaut_app/tasks/routing_tasks.py)
  and [upload_tasks.py](../../../cosmonaut_app/tasks/upload_tasks.py).
- **`sync_files=False` on save**: skip the upload when several saves happen in quick succession and
  only the last needs to sync (e.g. delete → upload → save would otherwise trigger 3+ rclone syncs).

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

- **Do** pass `sync_files=False` when loading a job inside a web (Dash) callback.
- **Do** load with `overwrite=True` inside Celery tasks.
- **Don't** assume `street_processing` is a status string — it may be a Celery task ID.
- **Don't** add a field to `JobModel` expecting it in the `config` JSONB (or vice-versa): the split
  is by membership in `FullPipelineConfig.model_fields`, not by where you declare it.
- **Don't** write to `working_dir` and forget to `save()` — unsynced files never reach MinIO and are
  lost when the stateless web pod restarts.

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
