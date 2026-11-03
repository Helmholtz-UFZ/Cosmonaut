"""Upload post-processing tasks for COSMONAUT App.

This module contains Celery tasks for processing membership uploads.
After the web process validates and saves the membership file, these tasks
handle the heavy operations: OSM road network download and CRS projection.
"""

import logging
import os

import ijson
import requests.exceptions
import urllib3.exceptions
from celery import Task
from cosmo_ecosystem import job_persistence
from sensor_routing.constants import MEMBERSHIP_FILENAME
from sqlalchemy.exc import SQLAlchemyError

from cosmonaut_app.config import MAINTAINER_EMAIL
from cosmonaut_app.constants.general import OSM_DATA_DOWNLOAD_FILE
from cosmonaut_app.cosmonaut_job import CosmonautJob, _transform_csv
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.email_service import send_mail
from cosmonaut_app.error_handling import JobNotFound
from cosmonaut_app.osm import OsmDownloader
from cosmonaut_app.osm.source import OverpassRuntimeError
from cosmonaut_app.street_selector import file_sha256

log = logging.getLogger(__name__)

UPLOAD_MAX_RETRIES = 3


class UploadTask(Task):
    """Base class for upload processing tasks with custom error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure by marking street_processing as FAILED."""
        log.error(f"Upload task {task_id} failed: {exc}")
        # This is not defensive programming designed intentionally like this.
        job_id = args[0] if args else kwargs.get("job_id")
        if job_id:
            log.error(f"Upload processing for job {job_id} failed: {str(exc)}")


def process_upload_task(self, job_id, epsg_input):
    """Celery task to process membership upload post-processing.

    Downloads OSM road data and saves the result. This offloads the
    memory-intensive OSM download from the web server process.

    The task owns only the street processing state of the job's row
    (``membership_upload``): it uploads the work dir and writes that column,
    never the whole row, because the job was loaded before a download that can
    take minutes and the user may change the job meanwhile.

    Args:
        job_id: ID of the job to process.
        epsg_input: EPSG code of the uploaded membership data.
    """
    log.info(f"Starting upload processing task for job_id={job_id}")

    job = CosmonautJob(job_id=job_id)

    try:
        job_persistence.work_dir(job.job_id)
        membership_path = os.path.join(job.working_dir, MEMBERSHIP_FILENAME)
        classification_data = _transform_csv(membership_path, epsg_input, 4326)

        osm = OsmDownloader(classification_data, epsg_output=epsg_input)
        osm.run_osm_query(job.working_dir)
        log.info(f"OSM roads queried and saved for job {job_id}")

        # Once per download: the identity street edits and derived files are
        # checked against (street_selector).
        download_sha256 = file_sha256(
            os.path.join(job.working_dir, OSM_DATA_DOWNLOAD_FILE)
        )
        # Files first, row second (as job_persistence.save), but only the
        # column this task owns, re-read so a change made meanwhile survives.
        job_persistence.upload_work_dir(job_id)
        job = CosmonautJob(job_id=job_id)
        job.model.membership_upload["download_sha256"] = download_sha256
        job.model.membership_upload["street_processing"] = "COMPLETED"
        if _write_if_owner(job, self.request.id):
            log.info(f"Upload processing completed for job {job_id}")

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        urllib3.exceptions.ReadTimeoutError,
        # The response stream broke off mid-body (the stream is read lazily, so
        # this surfaces as the urllib3 error or as the parser's incomplete JSON)
        # or Overpass ended it with an in-band runtime error (partial data).
        urllib3.exceptions.ProtocolError,
        ijson.IncompleteJSONError,
        OverpassRuntimeError,
    ) as e:
        _retry_or_fail(self, job_id, e, f"Transient network error: {e}")

    except requests.exceptions.HTTPError as e:
        # NB: `if e.response` is wrong — requests.Response.__bool__ returns
        # `response.ok`, which is False for every status >= 400 (i.e. exactly the
        # transient codes below), so it would never retry. Test identity instead.
        if e.response is not None and e.response.status_code in (429, 502, 503, 504):
            _retry_or_fail(
                self,
                job_id,
                e,
                f"Overpass API transient error (HTTP {e.response.status_code})",
            )
        else:
            log.error(
                f"Error processing upload for job {job_id}: {str(e)}", exc_info=True
            )
            _fail_upload(job_id, self.request.id, e)
            raise

    except Exception as e:  # noqa: BLE001
        # Convention exception (CLAUDE.md: specific exceptions only): whatever
        # the task raises, street_processing must not stay PENDING and the
        # maintainer must hear of it. Re-raised below.
        log.error(f"Error processing upload for job {job_id}: {str(e)}", exc_info=True)
        _fail_upload(job_id, self.request.id, e)
        raise


def _retry_or_fail(task, job_id, error, reason):
    """Retry a transient error, or end the upload as failed once retries ran out.

    ``task.retry`` re-raises the error when ``max_retries`` is exhausted, which
    would skip the failure path; the exhausted case is therefore handled here,
    before the retry is asked for.
    """
    countdown = 2**task.request.retries * 5
    if task.request.retries >= UPLOAD_MAX_RETRIES:
        log.error(
            f"{reason} in upload processing for job {job_id}; "
            f"retries exhausted ({UPLOAD_MAX_RETRIES})."
        )
        _fail_upload(job_id, task.request.id, error)
        raise error
    log.warning(
        f"{reason} in upload processing for job {job_id}, "
        f"retry attempt {task.request.retries + 1}/{UPLOAD_MAX_RETRIES} "
        f"in {countdown}s"
    )
    task.retry(exc=error, countdown=countdown, max_retries=UPLOAD_MAX_RETRIES)


def _write_if_owner(job, task_id):
    """Write the job's ``membership_upload`` if ``task_id`` still owns the upload.

    A re-upload replaces the task id in the row; the task it superseded then
    finishes (or fails) without touching the newer upload's state.
    """
    written = DataBaseManager.update_membership_upload_of_task(
        job.job_id, task_id, job.model.membership_upload
    )
    if not written:
        log.warning(
            f"Upload task {task_id} no longer owns the upload of job {job.job_id}; "
            "its result is dropped."
        )
    return written


def _fail_upload(job_id, task_id, error):
    """Persist street_processing=FAILED with a column write, then tell the maintainer.

    A failed persist (job deleted meanwhile, database trouble) is logged and
    must not keep the maintainer mail from going out or mask ``error``, the one
    the caller re-raises. A task that no longer owns the upload writes nothing.
    """
    try:
        job = CosmonautJob(job_id=job_id)
        job.model.membership_upload["street_processing"] = "FAILED"
        _write_if_owner(job, task_id)
    except (JobNotFound, SQLAlchemyError):
        log.error(
            f"Could not persist FAILED street processing of job {job_id}",
            exc_info=True,
        )
    _notify_maintainer(job_id, error)


def _notify_maintainer(job_id, error):
    """Send email notification to maintainer on upload processing failure."""
    subject = f"COSMONAUT Upload Processing Failed: Job {job_id}"
    body = (
        f"Upload post-processing (OSM download / street selection) failed "
        f"for job {job_id}.\n\n"
        f"Error: {error}"
    )
    # send_mail never raises; a lost maintainer mail is logged there.
    send_mail(MAINTAINER_EMAIL, subject, body)
