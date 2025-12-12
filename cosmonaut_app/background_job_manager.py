"""Background job manager for COSMONAUT App.

This module provides a centralized manager for all background job operations using Celery.
It handles task registration, job submission, and status tracking.
"""

import logging

from celery import Celery

from cosmonaut_app.celery_config import CeleryConfig
from cosmonaut_app.tasks.routing_tasks import RoutingTask, process_routing_job

log = logging.getLogger(__name__)


class BackgroundJobManager:
    """Centralized manager for all background job operations using Celery."""

    def __init__(self):
        """Initialize the background job manager."""
        self.app = self._create_celery_app()
        self._register_tasks()

    def _create_celery_app(self):
        """Create and configure Celery application.

        Returns:
            Celery: Configured Celery application instance
        """
        app = Celery("cosmonaut")
        app.config_from_object(CeleryConfig)
        return app

    def _register_tasks(self):
        """Register task functions with Celery app.

        This dynamically registers all task functions as Celery tasks,
        making them available for background execution.
        """
        self.routing_task = self.app.task(
            bind=True,
            base=RoutingTask,
            name="cosmonaut_app.tasks.routing_tasks.process_routing",
        )(process_routing_job)

    def submit_routing_job(self, job):
        """Submit a routing job to the Celery queue.

        Args:
            job: CosmonautJob instance to submit

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        try:
            result = self.routing_task.apply_async(
                args=[job.job_id],  # Pass job_id, not job object (serialization)
                queue="routing",
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 60,  # First retry after 60s
                    "interval_step": 60,  # Increment by 60s each retry
                    "interval_max": 300,  # Max 300s between retries
                },
            )
            log.info(f"Submitted routing job {job.job_id} with task_id={result.id}")
            return result.id, False
        except Exception as e:
            log.error(f"Failed to submit routing job {job.job_id}: {str(e)}")
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
        from celery.result import AsyncResult

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
        """
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

    def revoke_job(self, task_id, terminate=False):
        """Revoke/cancel a running or queued task.

        Args:
            task_id: The Celery task ID
            terminate: If True, send SIGTERM to worker process (kill)
                       If False, just prevent execution (cancel)
        """
        self.app.control.revoke(task_id, terminate=terminate)
        log.info(f"{'Killed' if terminate else 'Cancelled'} task {task_id}")


# Lazy initialization pattern - singleton instance
_background_job_manager = None


def get_background_job_manager():
    """Get the global BackgroundJobManager instance (lazy instantiation).

    Returns:
        BackgroundJobManager: The singleton instance
    """
    global _background_job_manager
    if _background_job_manager is None:
        _background_job_manager = BackgroundJobManager()
    return _background_job_manager


# Expose Celery app for worker command
def make_celery():
    """Create Celery app for worker command.

    This is used by the Celery worker command line:
    celery -A cosmonaut_app.background_job_manager.celery worker ...

    Returns:
        Celery: Configured Celery application instance
    """
    manager = get_background_job_manager()
    return manager.app


celery = make_celery()
