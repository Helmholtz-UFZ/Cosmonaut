"""Test the routing job's run lifecycle: status in the job row, log in the job log.

The job row is the only source of a job's status (cosmo-ecosystem ADR 0002); the
log of the latest run is the job log in the database (``cosmo_ecosystem.job_log``),
readable from any pod. Runs against real Postgres and object storage. Outcomes
only: what the route computation page shows, the job row, the job log.
"""

import importlib
import logging
from unittest import mock

import dash
import pytest
from cosmo_ecosystem import job_persistence
from cosmo_ecosystem.job_log import JobLogHandler

from cosmonaut_app.constants.general import (
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.tasks.routing_tasks import process_routing_job
from test.help_functions_tests import another_pod_meanwhile


@pytest.fixture(scope="module")
def route_computation():
    """Return the route computation page module.

    Page modules call ``register_page`` at import, which needs a Dash app with
    pages enabled to exist first, so it is imported here rather than at the top
    of the module (a deliberate departure from the top-level import rule).
    """
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("cosmonaut_app.pages.route_computation")


@pytest.fixture
def running_job():
    """Yield a saved RUNNING job with a Celery task id; remove it afterwards."""
    job = CosmonautJob()
    job.model.status = JOB_STATUS_RUNNING
    job.model.submitted = True
    job.model.celery_task_id = "task-of-a-test"
    job.model.email = "test@ufz.de"
    job.save()
    yield job
    job_persistence.delete_job(job.job_id)


def _celery_says(status):
    """Patch the Celery state lookup to report status."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.get_job_status",
        return_value={"status": status},
    )


def _celery_must_not_be_asked():
    """Patch the Celery state lookup to fail the test when it is called."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.get_job_status",
        side_effect=AssertionError("the Celery state was consulted"),
    )


def _log_to_job_log(job_id, message):
    """Write message to the job's job log, as a worker's job run does."""
    logger = logging.getLogger("test.worker.job_run")
    handler = JobLogHandler(job_id)
    logger.addHandler(handler)
    try:
        logger.info(message)
    finally:
        logger.removeHandler(handler)
        handler.close()


@pytest.mark.parametrize("celery_status", ["SUCCESS", "FAILURE", "REVOKED"])
def test_a_running_job_shows_its_rows_status_whatever_celery_says(
    running_job, route_computation, celery_status
):
    with _celery_says(celery_status):
        shown = route_computation.update_status(1, None, running_job.job_id)

    assert shown["badge_text"] == JOB_STATUS_RUNNING
    row = DataBaseManager.get_job_columns(running_job.job_id)
    assert row["status"] == JOB_STATUS_RUNNING


def test_the_page_shows_a_running_jobs_log_records_on_a_pod_without_its_files(
    running_job, route_computation
):
    _log_to_job_log(running_job.job_id, "Projected 12 features to EPSG 25832")

    with another_pod_meanwhile(running_job):
        shown = route_computation.update_status(1, None, running_job.job_id)

    assert "Projected 12 features to EPSG 25832" in shown["log_content"]


def test_a_cancel_shows_failed_on_the_next_poll_with_the_cancel_in_the_job_log(
    running_job, route_computation
):
    job_id = running_job.job_id
    with _celery_must_not_be_asked():
        route_computation.cancel_computation(1, job_id)
        shown = route_computation.update_status(1, "status_check", job_id)

    assert shown["badge_text"] == JOB_STATUS_FAILED
    assert "run cancelled by user" in shown["log_content"]


def test_a_reset_of_a_running_job_leaves_an_empty_job_log(running_job):
    _log_to_job_log(running_job.job_id, "a line of the previous run")

    running_job.reset()

    job = CosmonautJob(job_id=running_job.job_id)
    assert job.get_status() == JOB_STATUS_PENDING
    assert job.get_logs() == ""


def test_a_failing_route_computation_ends_failed_and_still_notifies(running_job):
    """The job has no uploads, so the routing pipeline fails."""
    job_id = running_job.job_id

    process_routing_job(None, job_id)

    job = CosmonautJob(job_id=job_id)
    assert job.get_status() == JOB_STATUS_FAILED
    assert job.model.notified_end is True
    assert "Traceback" in job.get_logs()
