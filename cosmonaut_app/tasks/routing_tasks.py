"""Routing tasks for COSMONAUT App.

This module contains Celery tasks for processing routing jobs.
Currently implements a placeholder that computes a hash of parameters.
This will be replaced with actual routing algorithm implementation.
"""

import json
from time import sleep
import logging
import os
from logging.config import dictConfig

from celery import Task
from cosmonaut_app.constants import (
    SOLUTION_FILE,
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
        job_id = args[0] if args else kwargs.get("job_id")
        if job_id:
            log.error(f"Job {job_id} failed with error: {str(exc)}")


def routing_place_holder(output_dir):
    """Compute hash from parameters.json and write to file.

    This is a placeholder function that will be replaced with the actual
    routing algorithm implementation.

    Args:
        job_id: ID of the job to process

    Returns:
        str: SHA256 hash of the parameters
    """
    logging.info(f"Starting placeholder routing computation in {output_dir}")
    sleep(10)  # Simulate computation time
    result_file = os.path.join(output_dir, SOLUTION_FILE)
    with open(result_file, "w") as f:
        json.dump({"status": "completed"}, f)

    logging.info(f"Written placeholder solution to {result_file}")


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
    3. Call routing_place_holder() function
    4. Flush handlers and switch logging back to web config
    """
    from cosmonaut_app.config import DEBUG
    from cosmonaut_app.cosmonaut_job import CosmonautJob
    from cosmonaut_app.logger import (
        get_logger_config_computation,
        get_logger_config_web,
    )

    logging.info(f"Starting routing job task for job_id={job_id}")

    # Load job to get work directory
    job = CosmonautJob(job_id=job_id)

    # Switch logging to file in work directory
    dictConfig(
        get_logger_config_computation(os.path.join(job.output_dir, LOG_FILE_NAME))
    )

    try:
        logging.info(f"Starting routing job computation for job_id={job_id}")

        # TODO
        routing_place_holder(job.output_dir)

        # Post-processing: Create GPX and QR code
        logging.info(f"Starting post-processing for job {job.model.job_id}")
        qr_code_url = job.create_qr_code_routing()
        logging.info(f"Post-processing complete. QR code: {qr_code_url}")

        logging.info(f"Job {job_id} completed successfully")

        # Flush all handlers before switching back
        flush_all_handlers()

        # Switch logging back to web config
        dictConfig(get_logger_config_web(DEBUG))

        logging.info(f"Routing job {job_id} finished")

        job.model.status = JOB_STATUS_COMPLETED
        job.save()

    except Exception as e:
        logging.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)

        # Flush handlers and switch back even on error
        flush_all_handlers()
        dictConfig(get_logger_config_web(DEBUG))

        job.model.status = JOB_STATUS_FAILED
        job.save()

        raise
