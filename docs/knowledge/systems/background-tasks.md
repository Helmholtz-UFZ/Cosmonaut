# Background tasks

Resource-intensive work — OSM download and route computation — runs off the web process in Celery
workers, brokered by Redis. The web pod stays responsive and stateless; the worker does the heavy
lifting and persists results to Postgres + object storage. This page covers how jobs get onto a queue and how
their status flows back to the UI.

## Queues

Web process and worker run the one Celery app the framework assembles
(`cosmo_ecosystem.celery_app`) from [domain.py](../../../cosmonaut_app/domain.py), the module
`COSMO_DOMAIN` names. Each of its task specs names the task's queue; routes, the worker's queues
and the beat schedule all come from the specs. The framework adds its cleanup, the lost-run sweep
and the test task:

| Queue | Task | Work |
|-------|------|------|
| `upload` | [upload_tasks.py](../../../cosmonaut_app/tasks/upload_tasks.py) | `process_upload` — OSM download + projection for the job's area |
| `routing` | [routing_tasks.py](../../../cosmonaut_app/tasks/routing_tasks.py) | `process_routing` — run sensor-routing, build GPX + QR, notify |
| `maintenance` | framework `cleanup` | nightly at 03:00 UTC: logs older than 30 days, then jobs past their retention window |
| `maintenance` | framework `sweep_lost_runs` | on the framework's beat: RUNNING rows whose heartbeat is stale become `FAILED`, with a "Worker lost" line in the job log (schedule and threshold: cosmo-ecosystem ADR 0004) |
| `test` | framework `long_running_test` | a sleep task for worker/health testing |

The worker runs `celery -A cosmo_ecosystem.celery_app.celery worker --beat` without `--queues`.
The domain module and everything it imports (the tasks, `cosmonaut_job`, `submissions`) must not
touch the Celery app or the manager at import: assembly imports the domain module, so that would
assemble the app while the domain module is half-imported. They reach the manager at call time
through `submissions.manager()` (cosmo-ecosystem `docs/conventions/domain_module.md`).

## Submitting work

`submissions.submit_routing_job()` / `submit_upload_job()` call the framework manager's
`submit_job` / `submit_named_job`, which `send_task(name, args=[job_id, …], queue=…)`
with a retry policy, and stash `task_name:<id>` in Redis (24 h TTL) so a later revoked-task lookup can
recover the name. They return `(task_id, failed)`; the caller stores `task_id` on the job. The worker
**re-loads the job by id and calls `job_persistence.work_dir(job_id)`** — it never receives the job object over the wire, only
the id, and pulls a current copy from object storage (see [cosmonaut-job](../concepts/cosmonaut-job.md)).

The canonical submit path is `CosmonautJob.submit()`: `save()` (so the worker sees current files +
`parameters.json`), queue the run with `job_run.mark_queued` (`RUNNING` and `heartbeat_at = NULL` in
one write, before the enqueue), enqueue, then store `celery_task_id` with `update_columns`. Never
write `RUNNING` yourself: the run claims only a RUNNING row without a heartbeat.
An enqueue that reports failure writes `FAILED` and "Cannot start job <id>." to the job log.

## Status lives in the job row (cosmo-ecosystem ADR 0002)

Workers do **not** push status to the web pod, and the web pod does **not** ask Celery for a
route computation's status. The job row is the only source:

- `process_routing_job` runs the computation through `cosmo_ecosystem.job_run.run`, which first
  claims the queued row (gives it its first heartbeat), refreshes `heartbeat_at` while it
  computes, then writes `COMPLETED` (after uploading the work dir) or `FAILED`, and captures the job
  log in the database (`cosmo_ecosystem.job_log`), readable from any pod while the run goes on. A
  failed run ends as a *successful* Celery task; the end mail runs after `run` for both outcomes.
- A delivery that loses the claim (a redelivery after a pod died, a stale message after a reset until the
  job is resubmitted, the still-queued message of a cancelled job) is dropped: `run` returns `None`, writes nothing, and the
  task returns without end mail or `notified_end` (cosmo-ecosystem ADR 0004).
- A run killed hard (OOM, pod restart, `terminate=True`) stops its heartbeat; the framework sweep
  ends it as `FAILED` (interval and threshold: `job_run.HEARTBEAT_INTERVAL_SECONDS`,
  `sweep_tasks.LOST_RUN_THRESHOLD`, cosmo-ecosystem
  `docs/adr/0004-lost-job-runs-are-swept-not-retried.md`). Nothing is retried; the user resets and
  resubmits.
- `CosmonautJob.get_status()` reads the row only; `get_logs()` returns `job_log.read`.
- `CosmonautJob.cancel()` (cancel button, and `reset()` of a RUNNING job) revokes the task, then writes
  `FAILED` and a "run cancelled by user" record via `job_log.append`: a terminated worker writes nothing.
  `reset()` returns the row to `PENDING` with no heartbeat through `job_run.mark_pending`.
- `heartbeat_at` belongs to the run: it is no `JobModel` field, so `save()` of a loaded job never
  writes an older heartbeat back.
- `CosmonautJob.get_street_processing_status()` still asks Celery, for the upload task only, reading
  the task ID stored in `membership_upload["street_processing"]` (see the overloaded-field note in
  [cosmonaut-job](../concepts/cosmonaut-job.md)).

## Error handling and retries

- `UploadTask` implements `on_failure` to log against the job id. The routing task needs none: `run`
  turns every failure into `FAILED` in the row and never re-raises.
- `process_upload_task` retries transient network/Overpass errors (`ConnectionError`, `Timeout`,
  `ReadTimeoutError`, and HTTP 429/502/503/504) with exponential backoff, max 3; other errors mark
  `street_processing=FAILED` and email the maintainer. (See the `e.response is not None` gotcha in
  [osm-backend](osm-backend.md).)
- `revoke_job(task_id, terminate=True)` cancels/kills a task — used by `cancel()` and `delete_membership()`.

## Do / Don't

- **Do** pass only the `job_id` to a task and re-load and `job_persistence.work_dir()` inside it.
- **Do** `save()` before enqueuing so the worker's object storage pull is current.
- **Don't** expect the worker to update the UI directly — the web side polls the job row.
- **Don't** derive a route computation's status from Celery; read the job row (ADR 0002).
- **Don't** pass user input into task args that become object-storage keys; derive keys server-side from
  the validated `job_id`.

## Related links

- Code: [domain.py](../../../cosmonaut_app/domain.py),
  [submissions.py](../../../cosmonaut_app/submissions.py),
  [tasks/](../../../cosmonaut_app/tasks/)
- Concept: [cosmonaut-job](../concepts/cosmonaut-job.md) (`submit()`, `cancel()`, `work_dir`)
- Systems: [osm-backend](osm-backend.md) (`upload` queue work),
  [sensor-routing-integration](sensor-routing-integration.md) (`routing` queue work)
- Overview: [architecture.md](../../architecture.md)
