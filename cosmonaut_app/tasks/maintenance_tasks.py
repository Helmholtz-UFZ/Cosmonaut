"""Maintenance tasks for periodic cleanup and database management.

This module provides Celery tasks for cleaning up expired jobs and old logs.
Tasks can be run manually or scheduled via Celery Beat.

Job cleanup itself is ``cosmo_ecosystem.job_retention.clean_up_jobs``; only the
task, its name and the app's own log retention period live here.
"""

import logging
from dataclasses import asdict
from datetime import datetime, timedelta

from celery import Task
from cosmo_ecosystem.job_retention import clean_up_jobs

from cosmonaut_app.constants.general import LOG_RETENTION_DAYS
from cosmonaut_app.db_manager import DataBaseManager

log = logging.getLogger(__name__)


class MaintenanceTask(Task):
    """Base class for maintenance tasks with custom error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure.

        Args
        ----
        exc : Exception
            Exception that caused the failure
        task_id : str
            Celery task ID
        args : tuple
            Task positional arguments
        kwargs : dict
            Task keyword arguments
        einfo : ExceptionInfo
            Exception info object with traceback
        """
        log.error(f"Maintenance task {task_id} failed: {exc}")
        log.error(f"Traceback: {einfo}")


def cleanup_task(self) -> dict:
    """Celery task for periodic cleanup of logs and jobs.

    This task performs:
    1. Log cleanup (old log entries from PostgreSQL)
    2. Job cleanup (database, local work dirs, object storage), via the framework

    Logs go first: job cleanup may raise ``JobCleanupFailed``, and log retention
    in a ``finally`` could replace that exception with its own and hide which
    jobs failed.

    Returns
    -------
    dict
        The framework's ``CleanupSummary`` as a dict (deleted_ids, kept_ids,
        failed_ids, removed_local_dirs). A dict, not the dataclass, because
        Celery stores the result as JSON.

    Raises
    ------
    JobCleanupFailed
        After the run, if any expired job could not be deleted; the task is then
        marked failed.
    """
    log.info("Starting maintenance cleanup task")

    cutoff_datetime = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    log.info(
        f"Cleaning up logs older than {LOG_RETENTION_DAYS} days "
        f"(before {cutoff_datetime})"
    )
    deleted_count = DataBaseManager.delete_logs_older_than(cutoff_datetime)
    log.debug(f"Deleted {deleted_count} old log entries from database")

    return asdict(clean_up_jobs())
