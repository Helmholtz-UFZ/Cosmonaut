"""Background job manager for COSMONAUT App.

Extends ``cosmo_suite.background_job_manager.BackgroundJobManager``: the generic
plumbing (``submit_job``, ``submit_named_job``, ``get_job_status``,
``get_task_result_info``, ``get_all_tasks_overview``, ``revoke_job``,
``submit_test_task``) comes from the framework; only the domain submissions are
added here.

``track_task_name`` defaults to True in both submit helpers, which is what keeps a
revoked task from showing up as "Unknown" on the worker-management page — this app
relied on that Redis write before the framework had the seam, so nothing needs to
pass it explicitly.

Task registration lives in celery_app.py (the worker entry point) to avoid a
circular import: tasks/*.py -> cosmonaut_job -> this module -> tasks/*.py.
"""

import logging
from logging.config import dictConfig

from celery.signals import worker_process_init
from cosmo_suite.background_job_manager import NAME_TEST_TASK as NAME_TEST_TASK
from cosmo_suite.background_job_manager import (
    BackgroundJobManager as BaseBackgroundJobManager,
)
from cosmo_suite.background_job_manager import (
    configure_worker_logging as framework_configure_worker_logging,
)
from cosmo_suite.logger import get_logger_config_worker

from cosmonaut_app.celery_config import CeleryConfig
from cosmonaut_app.constants.general import EXCLUDED_LOG_PACKAGES

log = logging.getLogger(__name__)

# The framework module connects its own worker_process_init handler on import.
# Both would run and the last one would win, i.e. the effective worker logging
# config would depend on import order. Disconnect it explicitly: cosmonaut needs
# its own excluded-packages list (matplotlib/PIL/pyogrio/rasterio all run inside
# worker processes), see logger.py.
worker_process_init.disconnect(framework_configure_worker_logging)


@worker_process_init.connect
def configure_worker_logging(sender=None, conf=None, **kwargs):
    """Configure database logging for Celery worker processes."""
    dictConfig(get_logger_config_worker(EXCLUDED_LOG_PACKAGES))


NAME_ROUTING_TASK = "cosmonaut_app.tasks.routing_tasks.process_routing"
NAME_MAINTENANCE_CLEANUP_TASK = "cosmonaut_app.tasks.maintenance_tasks.cleanup"
NAME_UPLOAD_TASK = "cosmonaut_app.tasks.upload_tasks.process_upload"


class BackgroundJobManager(BaseBackgroundJobManager):
    """Cosmonaut's job manager: framework plumbing + the domain submissions."""

    def __init__(self):
        """Build the framework manager, then re-point it at cosmonaut's config."""
        super().__init__()
        # CeleryConfig subclasses BaseCeleryConfig, so this only adds the domain
        # queues/beat schedule and drops the framework's task time limits.
        self.app.config_from_object(CeleryConfig)

    def submit_routing_job(self, job) -> tuple[str | None, bool]:
        """Submit a routing job to the Celery queue.

        Args:
            job: CosmonautJob instance to submit

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        return self.submit_job(NAME_ROUTING_TASK, job.model.job_id, "routing")

    def submit_upload_job(self, job, epsg_input: int) -> tuple[str | None, bool]:
        """Submit an upload post-processing job to the Celery queue.

        Args:
            job: CosmonautJob instance to submit
            epsg_input: EPSG code of the uploaded membership data

        Returns:
            tuple: (celery_task_id, failed_boolean)
                   celery_task_id is None if submission failed
        """
        # submit_named_job, not submit_job: the framework's submit_job passes the
        # job id as the task's *only* positional arg, and this task takes a second
        # one. Same retry policy and the same task-name tracking underneath.
        return self.submit_named_job(
            NAME_UPLOAD_TASK,
            args=[job.model.job_id, epsg_input],
            queue="upload",
        )

    def submit_cleanup_task(self) -> tuple[str | None, bool]:
        """Submit cosmonaut's maintenance cleanup task.

        Overrides the framework method, which submits
        ``cosmo_suite.tasks.maintenance_tasks.cleanup`` — that task cleans up via
        cosmo_suite.db_manager, which this app does not use.
        """
        return self.submit_named_job(NAME_MAINTENANCE_CLEANUP_TASK, queue="default")


_background_job_manager = None


def __getattr__(name):
    """Lazy singleton — BackgroundJobManager is created on first access, not on import."""
    global _background_job_manager
    if name == "background_job_manager":
        if _background_job_manager is None:
            _background_job_manager = BackgroundJobManager()
        return _background_job_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
