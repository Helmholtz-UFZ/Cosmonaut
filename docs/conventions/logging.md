# Logging Conventions

## Proper Logger Usage

```python
import logging

log = logging.getLogger(__name__)

log.info("message")
log.debug("message")
log.warning("message")
log.error("message", exc_info=True)
```

**DO NOT use:** `extra={"tag": "..."}` - this is a legacy pattern, do not copy.

---

## Log Levels

### DEBUG
Variable values, state transitions, diagnostic details.
```python
log.debug(f"load job with id {job_id}")
log.debug(f"Validating email: {value}")
```

### INFO
Major workflow steps, successful operations.
```python
log.info(f"Starting routing job for {job_id}")
log.info(f"Save job {self.model.job_id}")
log.info(f"Job {job_id} reset successfully")
```

### WARNING
Degraded states, retries, skipped operations.
```python
log.warning(f"Database OperationalError: {e}")
log.warning(f"Cannot delete - job status is {status}")
log.warning(f"Job already running, ignoring start")
```

### ERROR
Failures, exceptions, critical issues. Use `exc_info=True` for stack traces.
```python
log.error(f"Failed to submit job {job_id}")
log.error(f"Error processing job: {str(e)}", exc_info=True)
```

---

## Best Practices

1. **Always include identifiers** in messages:
   ```python
   log.info(f"Job {job_id} completed")  # Good
   log.info("Job completed")            # Bad - which job?
   ```

2. **Use appropriate level**:
   - Retrying? → WARNING
   - User input invalid? → DEBUG (not ERROR)
   - Operation failed? → ERROR

3. **Include stack traces** for errors:
   ```python
   log.error(f"Error: {e}", exc_info=True)
   ```

---

## Logger Configuration

Configuration is in `cosmonaut_app/logger.py`:
- Web/worker: Console + PostgreSQL database logging
- Computation tasks: File-based logging in job output directory
- Third-party package filtering to reduce noise

---

## Logs in Test Artifacts

When a Playwright test fails, the `page` fixture in `test/conftest.py` captures all
Python log output (including Dash callbacks, werkzeug requests, and application logs)
into `test/artifacts/<test-dir>/server.log`. This uses a `logging.Handler` that
collects records during the test and writes them on failure.

This means every `log.info(...)`, `log.error(...)`, etc. from your application code
is available for post-mortem debugging without re-running the test.

See [Testing conventions — Test Artifacts](testing.md#test-artifacts) for the full
artifact reference.

---

## Celery and the Root Logger

The web process runs a Celery Beat thread (`app.py`). By default Celery hijacks the
root logger on startup, replacing all handlers with its own stdout-only handler. This
silently drops the PostgreSQL handler.

**Always keep this in `CeleryConfig`:**

```python
worker_hijack_root_logger = False
```

Without it, logs appear in the container stdout (in Celery format) but never reach
the database, and the `/logs` page shows nothing.
