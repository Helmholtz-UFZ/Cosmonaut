"""Routing tasks for COSMONAUT App.

This module contains Celery tasks for processing routing jobs.
Currently implements a placeholder that computes a hash of parameters.
This will be replaced with actual routing algorithm implementation.
"""

import logging
import os
from logging.config import dictConfig

from celery import Task
from sensor_routing.full_pipeline_cli import sensor_routing_pipeline

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    LOG_FILE_NAME,
)

log = logging.getLogger(__name__)


class RoutingTask(Task):
    """Base class for routing tasks with custom error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        log.error(f"Task {task_id} failed: {exc}")
        # This is not defensive programming designed intentionally like this.
        job_id = args[0] if args else kwargs.get("job_id")
        if job_id:
            log.error(f"Job {job_id} failed with error: {str(exc)}")


def flush_all_handlers():
    """Flush all logging handlers."""
    logger = logging.getLogger()
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def process_routing_job(self, job_id):
    """Celery task to process a routing job.

    Args:
        job_id: ID of the job to process

    Steps:
    1. Load job from database
    2. Switch logging to file in work_dir (mimicking cosmopolitan's computation_tasks)
    3. Call sensor_routing_pipeline() function
    4. Flush handlers and switch logging back to web config
    """
    from cosmonaut_app.cosmonaut_job import CosmonautJob
    from cosmonaut_app.logger import (
        get_logger_config_computation,
        get_logger_config_worker,
    )

    logging.info(f"Starting routing job task for job_id={job_id}")

    # Load job to get work directory
    job = CosmonautJob(job_id=job_id)

    # Switch logging to file in work directory
    dictConfig(
        get_logger_config_computation(os.path.join(job.working_dir, LOG_FILE_NAME))
    )

    try:
        logging.info(f"Starting routing job computation for job_id={job_id}")

        sensor_routing_pipeline(job.working_dir)

        # Post-processing: Create GPX and QR code
        logging.info(f"Starting post-processing for job {job.model.job_id}")
        qr_code_url = job.create_qr_code_routing()
        logging.info(f"Post-processing complete. QR code: {qr_code_url}")

        logging.info(f"Job {job_id} completed successfully")

        # Flush all handlers before switching back
        flush_all_handlers()

        # Switch logging back to web config
        dictConfig(get_logger_config_worker())

        logging.info(f"Routing job {job_id} finished")

        job.model.status = JOB_STATUS_COMPLETED
        job.save()

        _notify_user(job, JOB_STATUS_COMPLETED)

    except Exception as e:
        logging.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)

        # Flush handlers and switch back even on error
        flush_all_handlers()
        dictConfig(get_logger_config_worker())

        job.model.status = JOB_STATUS_FAILED
        job.save()

        _notify_user(job, JOB_STATUS_FAILED)

        raise


def _notify_user(job, status):
    """Send email notification to user if email is set and not yet notified."""
    if not job.model.email or job.model.notified_end:
        return

    from cosmonaut_app.config import get_download_url
    from cosmonaut_app.email_service import send_mail

    job_id = job.model.job_id

    if status == JOB_STATUS_COMPLETED:
        download_url = get_download_url(job_id)
        subject = f"COSMONAUT Job {job_id} completed"
        body = (
            f"Your routing job {job_id} has completed successfully.\n\n"
            f"Download your results: {download_url}"
        )
    else:
        subject = f"COSMONAUT Job {job_id} failed"
        body = f"Your routing job {job_id} has failed. Please check the application for details."

    try:
        send_mail([job.model.email], subject, body)
        job.model.notified_end = True
        job.save()
    except Exception:  # noqa - must not let email failure crash notification path
        log.error(f"Failed to send notification email for job {job_id}", exc_info=True)
