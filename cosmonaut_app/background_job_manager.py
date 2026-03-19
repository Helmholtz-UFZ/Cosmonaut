"""Background job manager for COSMONAUT App.

This module provides a centralized manager for all background job operations using Celery.
It handles job submission, status tracking, and task revocation.

Task registration lives in celery_app.py (the worker entry point) to avoid a
circular import: tasks/*.py → cosmonaut_job → this module → tasks/*.py.
"""

import logging
import time

from celery import Celery
from celery.result import AsyncResult
from kombu.exceptions import OperationalError

from cosmonaut_app.celery_config import CeleryConfig

log = logging.getLogger(__name__)

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

    def submit_routing_job(self, job):
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
        except Exception as e:
            log.error(f"Failed to submit routing job {job.model.job_id}: {str(e)}")
            return None, True

    def submit_upload_job(self, job, epsg_input):
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
        except Exception as e:
            log.error(f"Failed to submit upload job {job.model.job_id}: {str(e)}")
            return None, True

    def get_job_status(self, task_id):
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
        }

    def get_all_tasks_overview(self):
        """Get comprehensive task overview using Celery inspect API.

        Returns:
            dict: Contains active, reserved, scheduled, revoked tasks and worker list
                  - active: List of running tasks with worker field
                  - reserved: List of claimed but not started tasks
                  - scheduled: List of future-scheduled tasks
                  - revoked: List of revoked task IDs
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

            # Flatten task lists (they come grouped by worker)
            def flatten_tasks(task_dict):
                """Flatten task dict from {worker: [tasks]} to [tasks]."""
                flattened = []
                for worker, tasks in (task_dict or {}).items():
                    for task in tasks:
                        task["worker"] = worker
                        flattened.append(task)
                return flattened

            # Flatten revoked task IDs
            revoked_ids = []
            for worker, task_ids in revoked_dict.items():
                revoked_ids.extend(task_ids)

            # Get list of online workers
            workers = list(inspect.ping().keys()) if inspect.ping() else []

            return {
                "active": flatten_tasks(active),
                "reserved": flatten_tasks(reserved),
                "scheduled": flatten_tasks(scheduled),
                "revoked": revoked_ids,
                "workers": workers,
            }
        except (OperationalError, ConnectionError) as e:
            log.warning(f"Failed to connect to Celery broker: {str(e)}")
            raise ConnectionError(
                "Unable to connect to Celery broker. Ensure Redis is running and accessible."
            ) from e

    def revoke_job(self, task_id, terminate=False):
        """Revoke/cancel a running or queued task.

        Args:
            task_id: The Celery task ID
            terminate: If True, send SIGTERM to worker process (kill)
                       If False, just prevent execution (cancel)
        """
        self.app.control.revoke(task_id, terminate=terminate)
        log.info(f"{'Killed' if terminate else 'Cancelled'} task {task_id}")
        time.sleep(0.5)

    def submit_test_task(self):
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
        except Exception as e:
            log.error(f"Failed to submit test task: {str(e)}")
            return None, True

    def submit_cleanup_task(self):
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
        except Exception as e:
            log.error(f"Failed to submit cleanup task: {str(e)}")
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
