# Background tasks

Resource-intensive work — OSM download and route computation — runs off the web process in Celery
workers, brokered by Redis. The web pod stays responsive and stateless; the worker does the heavy
lifting and persists results to Postgres + MinIO. This page covers how jobs get onto a queue and how
their status flows back to the UI.

## Queues

[celery_config.py](../../../cosmonaut_app/celery_config.py) routes tasks by module:

```python
task_routes = {
    "cosmonaut_app.tasks.routing_tasks.*": {"queue": "routing"},
    "cosmonaut_app.tasks.upload_tasks.*":  {"queue": "upload"},
}
```

In practice four queues are used (submitters in
[background_job_manager.py](../../../cosmonaut_app/background_job_manager.py) also pass `queue=`
explicitly):

| Queue | Task module | Work |
|-------|-------------|------|
| `upload` | [upload_tasks.py](../../../cosmonaut_app/tasks/upload_tasks.py) | `process_upload` — OSM download + projection for the job's area |
| `routing` | [routing_tasks.py](../../../cosmonaut_app/tasks/routing_tasks.py) | `process_routing` — run sensor-routing, build GPX + QR, notify |
| `default` | [maintenance_tasks.py](../../../cosmonaut_app/tasks/maintenance_tasks.py) | `cleanup` — delete jobs past their retention window |
| `test` | `test_tasks.py` | a sleep task for worker/health testing |

Task **registration** lives in `celery_app.py` (the worker entry point), kept separate from
`background_job_manager.py` to avoid a circular import (`tasks/* → cosmonaut_job → background_job_manager → tasks/*`).
`background_job_manager` is a lazy singleton created on first attribute access, not at import time.

## Submitting work

`BackgroundJobManager.submit_routing_job()` / `submit_upload_job()` call `app.send_task(name, args=[job_id, …], queue=…)`
with a retry policy, and stash `task_name:<id>` in Redis (24 h TTL) so a later revoked-task lookup can
recover the name. They return `(task_id, failed)`; the caller stores `task_id` on the job. The worker
**re-loads the job by id with `overwrite=True`** — it never receives the job object over the wire, only
the id, and pulls a clean copy from MinIO (see [cosmonaut-job](../concepts/cosmonaut-job.md)).

The canonical submit path is `CosmonautJob.submit()`: set `status=RUNNING`, `save()` (so the worker
sees current files + `parameters.json`), enqueue, then store `celery_task_id` with `sync_files=False`.

## Status flows back lazily (no callbacks from the worker)

Workers do **not** push status to the web pod. Instead the job object pulls it from Celery on demand:

- `CosmonautJob.get_status()` — only if the job is `RUNNING` with a `celery_task_id`, query Celery and
  map `SUCCESS → COMPLETED`, `FAILURE`/`REVOKED → FAILED`, persisting the change.
- `CosmonautJob.get_street_processing_status()` — same idea for the upload task, reading the task ID
  stored in `membership_upload["street_processing"]` (see the overloaded-field note in
  [cosmonaut-job](../concepts/cosmonaut-job.md)).

So a page renders current status by *asking*, not by having been *told*. The task itself also writes a
terminal `status` in its own `try/except` (`COMPLETED`/`FAILED`) and sends the user email — the lazy
sync is the fallback for the window before the task's own write lands or when a task is revoked.

## Error handling and retries

- Both task base classes (`UploadTask`, `RoutingTask`) implement `on_failure` to log against the job id.
- `process_upload_task` retries transient network/Overpass errors (`ConnectionError`, `Timeout`,
  `ReadTimeoutError`, and HTTP 429/502/503/504) with exponential backoff, max 3; other errors mark
  `street_processing=FAILED` and email the maintainer. (See the `e.response is not None` gotcha in
  [osm-backend](osm-backend.md).)
- `revoke_job(task_id, terminate=True)` cancels/kills a task — used by `reset()` and `delete_membership()`.

## Do / Don't

- **Do** pass only the `job_id` to a task and re-load with `overwrite=True` inside it.
- **Do** `save()` before enqueuing so the worker's MinIO pull is current.
- **Don't** expect the worker to update the UI directly — the web side syncs status lazily via the job.
- **Don't** pass user input into task args that become object-storage keys; derive keys server-side from
  the validated `job_id`.

## Related links

- Code: [background_job_manager.py](../../../cosmonaut_app/background_job_manager.py),
  [celery_config.py](../../../cosmonaut_app/celery_config.py),
  [celery_app.py](../../../cosmonaut_app/celery_app.py),
  [tasks/](../../../cosmonaut_app/tasks/)
- Concept: [cosmonaut-job](../concepts/cosmonaut-job.md) (`submit()`, status sync, `overwrite` loads)
- Systems: [osm-backend](osm-backend.md) (`upload` queue work),
  [sensor-routing-integration](sensor-routing-integration.md) (`routing` queue work)
- Overview: [architecture.md](../../architecture.md)
