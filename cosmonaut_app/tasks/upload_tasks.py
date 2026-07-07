"""Upload post-processing tasks for COSMONAUT App.

This module contains Celery tasks for processing membership uploads.
After the web process validates and saves the membership file, these tasks
handle the heavy operations: OSM road network download and CRS projection.
"""

import logging
import os

import requests.exceptions
import urllib3.exceptions
from celery import Task
from sensor_routing.constants import MEMBERSHIP_FILENAME

from cosmonaut_app.config import MAINTAINER_EMAIL
from cosmonaut_app.cosmonaut_job import CosmonautJob, _transform_csv
from cosmonaut_app.email_service import send_mail
from cosmonaut_app.osm import OsmDownloader

log = logging.getLogger(__name__)


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

    Args:
        job_id: ID of the job to process.
        epsg_input: EPSG code of the uploaded membership data.
    """
    log.info(f"Starting upload processing task for job_id={job_id}")

    job = CosmonautJob(job_id=job_id, overwrite=True)

    try:
        membership_path = os.path.join(job.working_dir, MEMBERSHIP_FILENAME)
        classification_data = _transform_csv(membership_path, epsg_input, 4326)

        osm = OsmDownloader(classification_data, epsg_output=epsg_input)
        osm.run_osm_query(job.working_dir)
        log.info(f"OSM roads queried and saved for job {job_id}")

        job.model.membership_upload["street_processing"] = "COMPLETED"
        job.save()

        log.info(f"Upload processing completed for job {job_id}")

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        urllib3.exceptions.ReadTimeoutError,
    ) as e:
        countdown = 2 ** self.request.retries * 5
        log.warning(
            f"Transient network error in upload processing for job {job_id}, "
            f"retry attempt {self.request.retries + 1}/3 in {countdown}s: {str(e)}"
        )
        self.retry(exc=e, countdown=countdown, max_retries=3)

    except requests.exceptions.HTTPError as e:
        # NB: `if e.response` is wrong — requests.Response.__bool__ returns
        # `response.ok`, which is False for every status >= 400 (i.e. exactly the
        # transient codes below), so it would never retry. Test identity instead.
        if e.response is not None and e.response.status_code in (429, 502, 503, 504):
            countdown = 2 ** self.request.retries * 5
            log.warning(
                f"Overpass API transient error (HTTP {e.response.status_code}) "
                f"for job {job_id}, retry attempt {self.request.retries + 1}/3 in {countdown}s"
            )
            self.retry(exc=e, countdown=countdown, max_retries=3)
        else:
            log.error(
                f"Error processing upload for job {job_id}: {str(e)}", exc_info=True
            )
            job.model.membership_upload["street_processing"] = "FAILED"
            job.save()
            _notify_maintainer(job_id, e)
            raise

    except Exception as e:
        log.error(f"Error processing upload for job {job_id}: {str(e)}", exc_info=True)

        job.model.membership_upload["street_processing"] = "FAILED"
        job.save()

        _notify_maintainer(job_id, e)

        raise


def _notify_maintainer(job_id, error):
    """Send email notification to maintainer on upload processing failure."""
    subject = f"COSMONAUT Upload Processing Failed: Job {job_id}"
    body = (
        f"Upload post-processing (OSM download / street selection) failed "
        f"for job {job_id}.\n\n"
        f"Error: {error}"
    )
    try:
        send_mail(MAINTAINER_EMAIL, subject, body)
    except Exception:  # noqa - must not let email failure crash notification path
        log.error(
            f"Failed to send maintainer notification for job {job_id}", exc_info=True
        )
