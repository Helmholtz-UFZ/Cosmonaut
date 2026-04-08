"""Background job manager for COSMONAUT App.

This module provides a centralized manager for all background job operations using Celery.
It handles job submission, status tracking, and task revocation.

Task registration lives in celery_app.py (the worker entry point) to avoid a
circular import: tasks/*.py → cosmonaut_job → this module → tasks/*.py.
"""

import logging
from logging.config import dictConfig

from celery import Celery
from celery.exceptions import CeleryError
from celery.result import AsyncResult
from celery.signals import worker_process_init
from kombu.exceptions import OperationalError

from cosmonaut_app.celery_config import CeleryConfig
from cosmonaut_app.logger import get_logger_config_worker

log = logging.getLogger(__name__)


@worker_process_init.connect
def configure_worker_logging(sender=None, conf=None, **kwargs):
    """Configure database logging for Celery worker processes."""
    dictConfig(get_logger_config_worker())


NAME_ROUTING_TASK = "cosmonaut_app.tasks.routing_tasks.process_routing"
NAME_TEST_TASK = "cosmonaut_app.tasks.test_tasks.test_sleep"
NAME_MAINTENANCE_CLEANUP_TASK = "cosmonaut_app.tasks.maintenance_tasks.cleanup"
NAME_UPLOAD_TASK = "cosmonaut_app.tasks.upload_tasks.process_upload"


class BackgroundJobManager:
    """Centralized manager for all background job operations using Celery."""

    def __init__(self):
        """Initialize the background job manager."""
        self.app = Celery("cosmonaut")
        self.app.config_from_object(CeleryConfig)

    def submit_routing_job(self, job) -> tuple[str | None, bool]:
        """Submit a routing job to the Celery queue.

        Args:
            job: CosmonautJob instance to submit

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        try:
            result = self.app.send_task(
                NAME_ROUTING_TASK,
                args=[job.model.job_id],
                queue="routing",
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 10,
                    "interval_step": 15,
                    "interval_max": 30,
                },
            )
            # Store task name in Redis for revoked task retrieval
            self.app.backend.client.set(
                f"task_name:{result.id}",
                NAME_ROUTING_TASK,
                ex=86400,  # 24 hour TTL
            )
            log.info(
                f"Submitted routing job {job.model.job_id} with task_id={result.id}"
            )
            return result.id, False
        except (OperationalError, CeleryError) as e:
            log.error(f"Failed to submit routing job {job.model.job_id}: {e}")
            return None, True

    def submit_upload_job(self, job, epsg_input: int) -> tuple[str | None, bool]:
        """Submit an upload post-processing job to the Celery queue.

        Args:
            job: CosmonautJob instance to submit
            epsg_input: EPSG code of the uploaded membership data

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        try:
            result = self.app.send_task(
                NAME_UPLOAD_TASK,
                args=[job.model.job_id, epsg_input],
                queue="upload",
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 10,
                    "interval_step": 15,
                    "interval_max": 30,
                },
            )
            self.app.backend.client.set(
                f"task_name:{result.id}",
                NAME_UPLOAD_TASK,
                ex=86400,
            )
            log.info(
                f"Submitted upload job {job.model.job_id} with task_id={result.id}"
            )
            return result.id, False
        except (OperationalError, CeleryError) as e:
            log.error(f"Failed to submit upload job {job.model.job_id}: {e}")
            return None, True

    def get_job_status(self, task_id: str) -> dict:
        """Get status of a Celery task.

        Args:
            task_id: The Celery task ID

        Returns:
            dict: Task status information including:
                  - task_id: The task ID
                  - status: Task status (PENDING, STARTED, SUCCESS, FAILURE, etc.)
                  - result: Task result if ready, None otherwise
                  - traceback: Traceback if task failed, None otherwise
        """
        result = AsyncResult(task_id, app=self.app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
            "date_done": result.date_done,
        }

    def get_task_result_info(self, task_id: str) -> dict:
        """Get task name and status from result backend."""
        task_name = "Unknown"
        status = "REVOKED"

        try:
            result = AsyncResult(task_id, app=self.app)
            if result.name:
                task_name = result.name.split(".")[-1]
            else:
                stored_name = self.app.backend.client.get(f"task_name:{task_id}")
                if stored_name:
                    task_name = stored_name.decode().split(".")[-1]
            if result.status:
                status = result.status
        except CeleryError as e:
            log.debug(f"Could not get result info for task {task_id}: {e}")

        return {"task_name": task_name, "status": status}

    def get_all_tasks_overview(self) -> dict:
        """Get comprehensive task overview using Celery inspect API.

        Returns:
            dict: Contains active, reserved, scheduled, revoked tasks and worker list
                  - active: List of running tasks with worker field
                  - reserved: List of claimed but not started tasks
                  - scheduled: List of future-scheduled tasks
                  - revoked: List of revoked task dicts with "id" and "worker" keys
                  - workers: List of online worker names

        Raises:
            ConnectionError: If unable to connect to Redis/Celery broker
        """
        try:
            inspect = self.app.control.inspect()

            # Get task data from all workers
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            scheduled = inspect.scheduled() or {}
            revoked_dict = inspect.revoked() or {}

            def flatten_tasks(worker_dict):
                """Flatten {worker: [tasks]} to [tasks] with worker info."""
                result = []
                for worker, tasks in (worker_dict or {}).items():
                    for task in tasks:
                        if isinstance(task, dict):
                            task["worker"] = worker
                            result.append(task)
                        else:
                            # Revoked returns plain ID strings, not dicts
                            result.append({"id": task, "worker": worker})
                return result

            # Get list of online workers (single call to avoid race with worker shutdown)
            ping_result = inspect.ping()
            workers = list(ping_result.keys()) if ping_result else []

            return {
                "active": flatten_tasks(active),
                "reserved": flatten_tasks(reserved),
                "scheduled": flatten_tasks(scheduled),
                "revoked": flatten_tasks(revoked_dict),
                "workers": workers,
            }
        except (OperationalError, ConnectionError) as e:
            log.warning(f"Failed to connect to Celery broker: {str(e)}")
            raise ConnectionError(
                "Unable to connect to Celery broker. Ensure Redis is running and accessible."
            ) from e

    def revoke_job(self, task_id: str, terminate: bool = False) -> None:
        """Revoke/cancel a running or queued task.

        Args:
            task_id: The Celery task ID
            terminate: If True, send SIGTERM to worker process (kill)
                       If False, just prevent execution (cancel)
        """
        self.app.control.revoke(task_id, terminate=terminate)
        log.info(f"Task {task_id} revoked (terminate={terminate})")

    def submit_test_task(self) -> tuple[str | None, bool]:
        """Submit a test sleep task to the Celery queue.

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        try:
            result = self.app.send_task(
                NAME_TEST_TASK,
                queue="test",
            )
            # Store task name in Redis for revoked task retrieval
            self.app.backend.client.set(
                f"task_name:{result.id}",
                NAME_TEST_TASK,
                ex=86400,  # 24 hour TTL
            )
            log.info(f"Submitted test task with task_id={result.id}")
            return result.id, False
        except (OperationalError, CeleryError) as e:
            log.error(f"Failed to submit test task: {e}")
            return None, True

    def submit_cleanup_task(self) -> tuple[str | None, bool]:
        """Submit a maintenance cleanup task to the Celery queue.

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        try:
            result = self.app.send_task(
                NAME_MAINTENANCE_CLEANUP_TASK,
                queue="default",
            )
            # Store task name in Redis for revoked task retrieval
            self.app.backend.client.set(
                f"task_name:{result.id}",
                NAME_MAINTENANCE_CLEANUP_TASK,
                ex=86400,  # 24 hour TTL
            )
            log.info(f"Submitted cleanup task with task_id={result.id}")
            return result.id, False
        except (OperationalError, CeleryError) as e:
            log.error(f"Failed to submit cleanup task: {e}")
            return None, True


_background_job_manager = None


def __getattr__(name):
    """Lazy singleton — BackgroundJobManager is created on first access, not on import."""
    global _background_job_manager
    if name == "background_job_manager":
        if _background_job_manager is None:
            _background_job_manager = BackgroundJobManager()
        return _background_job_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
