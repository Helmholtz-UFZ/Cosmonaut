"""Routing tasks for COSMONAUT App.

The routing task runs the sensor-routing pipeline through the framework's job
run (``cosmo_ecosystem.job_run.run``), which captures the job log, fetches and
uploads the work dir and writes the final status to the job row. The job row is
the only source of the job's status (cosmo-ecosystem ADR 0002): a failed run
ends as FAILED in the row and as a successful Celery task.
"""

import logging
from datetime import timedelta

from cosmo_ecosystem import job_run
from cosmo_ecosystem.object_storage_manager import get_presigned_download_url
from sensor_routing.full_pipeline_cli import sensor_routing_pipeline

from cosmonaut_app.config import PORT, WEB_OUTSIDE_URL
from cosmonaut_app.constants.general import (
    EXCLUDED_LOG_PACKAGES,
    JOB_STATUS_COMPLETED,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.email_service import send_mail
from cosmonaut_app.error_handling import JobNotFound
from cosmonaut_app.street_selector import StreetSelector

log = logging.getLogger(__name__)


def process_routing_job(self, job_id):
    """Celery task to process a routing job.

    Runs the route computation as a job run (the submission mail included),
    then sends the end mail for either outcome, from the job's row as the run
    left it. A job deleted meanwhile gets no end mail and fails no task
    (cosmo-ecosystem ADR 0002: a run's outcome lives in the row, not in Celery).

    Args:
        job_id: ID of the job to process
    """
    log.info(f"Starting routing job task for job_id={job_id}")
    status = job_run.run(job_id, compute_route, EXCLUDED_LOG_PACKAGES)
    log.info(f"Routing job {job_id} finished with status {status}")

    try:
        job = CosmonautJob(job_id=job_id)
    except JobNotFound:
        log.info(f"Job {job_id} was deleted during its run; no end mail sent.")
        return
    _notify_user(job, status)


def compute_route(job_id, work_dir):
    """Compute the job's route, GPX and QR code into its work dir.

    The ``compute`` of the job run: it signals failure only by raising and
    writes no status; the run uploads the work dir and writes the status.
    The submission mail is sent here, not before the run, because it needs the
    job loaded, and a load failing outside the run would leave the row RUNNING.
    """
    log.info(f"Starting routing job computation for job_id={job_id}")
    job = CosmonautJob(job_id=job_id)
    _notify_submission(job)
    StreetSelector(job).ensure_projected()
    sensor_routing_pipeline(work_dir)

    log.info(f"Starting post-processing for job {job_id}")
    job.create_qr_code_routing()
    log.info(f"Post-processing complete. QR code generated for job {job_id}")


def _notify_submission(job):
    """Send email notification that job was submitted."""
    if not job.model.email:
        return

    job_id = job.model.job_id

    log.info(f"Send mail about submitted job {job_id}.")

    if "localhost" in WEB_OUTSIDE_URL:
        url_base = WEB_OUTSIDE_URL + ":" + PORT
    else:
        url_base = WEB_OUTSIDE_URL
    job_url = f"{url_base}/job/{job_id}/route-computation"

    subject = f"COSMONAUT Job {job_id} submitted"
    body = (
        f"Your routing job {job_id} has been submitted and is now being processed.\n\n"
        f"Check progress: {job_url}"
    )

    try:
        send_mail([job.model.email], subject, body)
    except Exception:  # noqa - must not let email failure crash submission path
        log.error(f"Failed to send submission email for job {job_id}", exc_info=True)


def _notify_user(job, status):
    """Send email notification to user if email is set and not yet notified."""
    if not job.model.email or job.model.notified_end:
        return

    job_id = job.model.job_id

    log.info(f"Send mail about finished job {job_id}.")

    if status == JOB_STATUS_COMPLETED:
        # Object key derived server-side from validated job_id — never pass user input here.
        object_key = f"{job_id}/route.gpx"
        download_url = get_presigned_download_url(object_key, expiry=timedelta(days=7))
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
        job.update_columns("notified_end")
    except Exception:  # noqa - must not let email failure crash notification path
        log.error(f"Failed to send notification email for job {job_id}", exc_info=True)
