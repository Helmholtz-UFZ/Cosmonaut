"""Routing tasks for COSMONAUT App.

This module contains Celery tasks for processing routing jobs.
Currently implements a placeholder that computes a hash of parameters.
This will be replaced with actual routing algorithm implementation.
"""

import hashlib
import json
import logging
import os
from logging.config import dictConfig

from celery import Task


log = logging.getLogger(__name__)


class RoutingTask(Task):
    """Base class for routing tasks with custom error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        log.error(f"Task {task_id} failed: {exc}")
        job_id = args[0] if args else kwargs.get("job_id")
        if job_id:
            log.error(f"Job {job_id} failed with error: {str(exc)}")


def compute_params_hash(job_id):
    """Compute hash from parameters.json and write to file.

    This is a placeholder function that will be replaced with the actual
    routing algorithm implementation.

    Args:
        job_id: ID of the job to process

    Returns:
        str: SHA256 hash of the parameters
    """
    from cosmonaut_app.cosmonaut_job import CosmonautJob

    # Load job
    job = CosmonautJob(job_id=job_id)

    # Read parameters.json (already dumped by job.save())
    params_file = os.path.join(job.input_dir, "parameters.json")
    with open(params_file, "r") as f:
        params = json.load(f)

    # Log parameters
    logging.info(f"Job {job_id} parameters: {json.dumps(params, indent=2)}")

    # Calculate hash
    params_str = json.dumps(params, sort_keys=True)
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()
    logging.info(f"Job {job_id} parameter hash: {params_hash}")

    # Write hash to file (minimal output per user preference)
    hash_file = os.path.join(job.output_dir, "params_hash.txt")
    with open(hash_file, "w") as f:
        f.write(f"{params_hash}\n")

    logging.info(f"Job {job_id} hash written to {hash_file}")

    # Save job (sync to object storage)
    job.save()

    return params_hash


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
    3. Call compute_params_hash() function
    4. Flush handlers and switch logging back to web config
    """
    from cosmonaut_app.config import DEBUG
    from cosmonaut_app.cosmonaut_job import CosmonautJob
    from cosmonaut_app.logger import (
        get_logger_config_computation,
        get_logger_config_web,
    )

    LOG_FILE_NAME = "worker.log"

    logging.info(f"Starting routing job task for job_id={job_id}")

    # Load job to get work directory
    job = CosmonautJob(job_id=job_id)

    # Switch logging to file in work directory
    dictConfig(
        get_logger_config_computation(os.path.join(job.working_dir, LOG_FILE_NAME))
    )

    try:
        logging.info(f"Starting routing job computation for job_id={job_id}")

        # Call the hash computation function (placeholder for routing algorithm)
        params_hash = compute_params_hash(job_id)

        logging.info(f"Job {job_id} completed successfully with hash: {params_hash}")

        # Flush all handlers before switching back
        flush_all_handlers()

        # Switch logging back to web config
        dictConfig(get_logger_config_web(DEBUG))

        logging.info(f"Routing job {job_id} finished")

        return {
            "status": "completed",
            "job_id": job_id,
            "hash": params_hash,
        }

    except Exception as e:
        logging.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)

        # Flush handlers and switch back even on error
        flush_all_handlers()
        dictConfig(get_logger_config_web(DEBUG))

        raise
