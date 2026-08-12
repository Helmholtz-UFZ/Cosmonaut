"""Maintenance tasks for periodic cleanup and database management.

This module provides Celery tasks for cleaning up expired jobs and old logs.
Tasks can be run manually or scheduled via Celery Beat.
"""

import logging
import os
import shutil
from datetime import date, datetime, timedelta

from celery import Task
from cosmo_suite.object_storage_manager import delete_directory_from_storage

from cosmonaut_app.config import (
    DAYS_DELETE_NOT_SUBMITTED,
    DAYS_DELETE_SUBMITTED,
    WEB_WORK_DIR,
)
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


def clean_up_jobs(
    days_delete_not_submitted=DAYS_DELETE_NOT_SUBMITTED,
    days_delete_submitted=DAYS_DELETE_SUBMITTED,
):
    """Delete jobs depending on their status and age.

    This function can be called programmatically from anywhere in the application
    or invoked via the Celery task wrapper.

    Parameters
    ----------
    days_delete_not_submitted : int
        Days to retain unsubmitted jobs (default: 2)
    days_delete_submitted : int
        Days to retain submitted jobs (default: 60)

    Returns
    -------
    dict
        Cleanup statistics with keys:
        - deleted_count: Number of jobs deleted
        - kept_count: Number of jobs kept
        - local_dirs_deleted: Number of local directories cleaned up
        - storage_dirs_deleted: Number of object storage directories deleted
    """
    log.info("Starting job cleanup task")

    kept_jobs = []
    deleted_jobs = []

    # Calculate cutoff dates
    cutoff_not_submitted = date.today() - timedelta(days=days_delete_not_submitted)
    cutoff_submitted = date.today() - timedelta(days=days_delete_submitted)

    # Query all jobs from database
    job_info_dict = DataBaseManager.list_jobs()
    log.debug(f"Found {len(job_info_dict)} total jobs in database")

    # Evaluate each job for deletion
    for job_id, job_info in job_info_dict.items():
        start_date = job_info["start_date"]
        submitted = job_info["submitted"]
        # Determine if job should be deleted
        should_delete = False
        if not submitted and start_date <= cutoff_not_submitted:
            should_delete = True
        elif start_date <= cutoff_submitted:
            should_delete = True

        if should_delete:
            DataBaseManager.delete_job(job_id)
            deleted_jobs.append(job_id)
        else:
            kept_jobs.append(job_id)

    log.debug(
        f"Database cleanup complete: {len(deleted_jobs)} deleted, {len(kept_jobs)} kept"
    )

    # Clean up local filesystem directories
    local_dirs_deleted = 0

    for dir_name in os.listdir(WEB_WORK_DIR):
        dir_path = os.path.join(WEB_WORK_DIR, dir_name)

        # Only delete directories, skip files
        if not os.path.isdir(dir_path):
            continue

        # Only delete if job was deleted from database
        if dir_name not in kept_jobs:
            log.debug(f"Deleting local directory: {dir_path}")
            shutil.rmtree(dir_path)
            local_dirs_deleted += 1

    log.debug(f"Local directory cleanup complete: {local_dirs_deleted} deleted")

    # Clean up object storage directories
    storage_dirs_deleted = 0

    for job_id in deleted_jobs:
        delete_directory_from_storage(job_id)
        storage_dirs_deleted += 1

    log.debug(f"Object storage cleanup complete: {storage_dirs_deleted} deleted")


def cleanup_task(self):
    """Celery task for periodic cleanup of jobs and logs.

    This task performs:
    1. Job cleanup (database, filesystem, object storage)
    2. Log cleanup (old log entries from PostgreSQL)

    Returns
    -------
    dict
        Cleanup statistics from both operations
    """
    log.info("Starting maintenance cleanup task")

    # Clean up jobs
    clean_up_jobs()

    # Clean up logs
    cutoff_datetime = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    log.info(
        f"Cleaning up logs older than {LOG_RETENTION_DAYS} days "
        f"(before {cutoff_datetime})"
    )

    deleted_count = DataBaseManager.delete_logs_older_than(cutoff_datetime)
    log.debug(f"Deleted {deleted_count} old log entries from database")
