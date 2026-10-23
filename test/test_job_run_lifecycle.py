"""Test the routing job's run lifecycle: status in the job row, log in the job log.

The job row is the only source of a job's status (cosmo-ecosystem ADR 0002); the
log of the latest run is the job log in the database (``cosmo_ecosystem.job_log``),
readable from any pod. Runs against real Postgres and object storage. Outcomes
only: what the route computation page shows, the job row, the job log.
"""

import contextlib
import importlib
import logging
from unittest import mock

import dash
import pytest
from cosmo_ecosystem import job_log, job_persistence
from cosmo_ecosystem.db_manager import DbManager
from cosmo_ecosystem.job_log import JobLogHandler
from pydantic import ValidationError
from sqlalchemy import update

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager, JobTable
from cosmonaut_app.tasks.routing_tasks import process_routing_job
from test.help_functions_tests import another_pod_meanwhile, celery_says


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


def _celery_must_not_be_asked():
    """Patch the Celery state lookup to fail the test when it is called."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.get_job_status",
        side_effect=AssertionError("the Celery state was consulted"),
    )


def _revoking_must_not_happen():
    """Patch the Celery revoke to fail the test when it is called."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.revoke_job",
        side_effect=AssertionError("a task was revoked"),
    )


def _enqueue_returns(celery_task_id, failed):
    """Patch the routing enqueue to report (celery_task_id, failed)."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.submit_routing_job",
        return_value=(celery_task_id, failed),
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
    with celery_says(celery_status):
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


def test_a_job_that_cannot_be_loaded_ends_failed_with_the_reason_in_its_job_log(
    running_job,
):
    job_id = running_job.job_id
    with DbManager.session_scope() as session:
        session.execute(
            update(JobTable)
            .where(JobTable.job_id == job_id)
            .values(street_edits={"removed_roads": "not a list of road ids"})
        )

    # The end mail needs the job loaded too, and fails the same way; the row
    # and the job log are what the user sees.
    with contextlib.suppress(ValidationError):
        process_routing_job(None, job_id)

    assert DataBaseManager.get_job_columns(job_id)["status"] == JOB_STATUS_FAILED
    assert "removed_roads" in job_log.read(job_id)


def test_a_job_deleted_during_its_run_ends_the_task_quietly(running_job):
    job_id = running_job.job_id

    def delete_the_job(work_dir):
        job_persistence.delete_job(job_id)

    with mock.patch(
        "cosmonaut_app.tasks.routing_tasks.sensor_routing_pipeline",
        side_effect=delete_the_job,
    ):
        process_routing_job(None, job_id)


def test_a_failed_enqueue_shows_failed_with_the_reason_in_the_job_log(running_job):
    job = CosmonautJob(job_id=running_job.job_id)
    job.model.status = JOB_STATUS_PENDING
    job.model.celery_task_id = None
    job.update_columns("status", "celery_task_id")

    with _enqueue_returns(None, True):
        job.submit()

    shown = CosmonautJob(job_id=job.job_id)
    assert shown.get_status() == JOB_STATUS_FAILED
    assert f"Cannot start job {job.job_id}." in shown.get_logs()


@pytest.mark.parametrize("finished_status", [JOB_STATUS_FAILED, JOB_STATUS_COMPLETED])
def test_a_restart_of_a_finished_job_revokes_no_task(
    running_job, route_computation, finished_status
):
    job_id = running_job.job_id
    running_job.model.status = finished_status
    running_job.update_columns("status")

    with _revoking_must_not_happen(), _enqueue_returns("task-of-the-restart", False):
        route_computation.restart_computation(1, job_id)

    assert CosmonautJob(job_id=job_id).get_status() == JOB_STATUS_RUNNING
