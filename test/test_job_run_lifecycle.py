"""Test the routing job's run lifecycle: status in the job row, log in the job log.

The job row is the only source of a job's status (cosmo-ecosystem ADR 0002); the
log of the latest run is the job log in the database (``cosmo_ecosystem.job_log``),
readable from any pod. Runs against real Postgres and object storage. Outcomes
only: what the route computation page shows, the job row, the job log.
"""

import contextlib
import importlib
import logging
import uuid
from unittest import mock

import dash
import pytest
from cosmo_ecosystem import job_log, job_persistence
from cosmo_ecosystem.db_manager import DbManager
from cosmo_ecosystem.job_log import JobLogHandler
from cosmo_ecosystem.job_run import CANCELLED_MESSAGE
from cosmo_ecosystem.object_storage_manager import ObjectStorageError
from pydantic import ValidationError
from sqlalchemy import func, update

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager, JobTable
from cosmonaut_app.tasks.routing_tasks import process_routing_job
from test.help_functions_tests import (
    another_pod_meanwhile,
    celery_says,
    remove_job,
    set_run_columns,
)


@pytest.fixture(scope="module")
def route_computation():
    """Return the route computation page module.

    Page modules call ``register_page`` at import, which needs a Dash app with
    pages enabled to exist first, so it is imported here rather than at the top
    of the module (a deliberate departure from the top-level import rule).
    """
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("cosmonaut_app.pages.route_computation")


@pytest.fixture(scope="module")
def route_download():
    """Return the route download page module (imported like route_computation)."""
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("cosmonaut_app.pages.route_download")


@pytest.fixture
def running_job():
    """Yield a saved RUNNING job with a Celery task id; remove it afterwards."""
    job = CosmonautJob()
    job.model.celery_task_id = "task-of-a-test"
    job.model.email = "test@ufz.de"
    job.save()
    set_run_columns(job.job_id, status=JOB_STATUS_RUNNING, submitted=True)
    yield job
    remove_job(job.job_id)


def _celery_must_not_be_asked():
    """Patch the Celery state lookup to fail the test when it is called."""
    return mock.patch(
        "cosmo_ecosystem.background_job_manager.background_job_manager.get_job_status",
        side_effect=AssertionError("the Celery state was consulted"),
    )


def _revoking_must_not_happen():
    """Patch the Celery revoke to fail the test when it is called."""
    return mock.patch(
        "cosmo_ecosystem.background_job_manager.background_job_manager.revoke_job",
        side_effect=AssertionError("a task was revoked"),
    )


def _enqueue_returns(celery_task_id, failed):
    """Patch the routing enqueue to report (celery_task_id, failed)."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.submit_routing_job",
        return_value=(celery_task_id, failed),
    )


def _give_the_row_a_heartbeat(job_id):
    """Set the row's heartbeat, as a job run that claimed it does."""
    with DbManager.session_scope() as session:
        session.execute(
            update(JobTable)
            .where(JobTable.job_id == job_id)
            .values(heartbeat_at=func.now())
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
    assert CANCELLED_MESSAGE in shown["log_content"]


def test_a_reset_of_a_running_job_leaves_an_empty_job_log(running_job):
    _log_to_job_log(running_job.job_id, "a line of the previous run")

    CosmonautJob(job_id=running_job.job_id).reset()

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
    set_run_columns(job.job_id, status=JOB_STATUS_PENDING)
    job.model.celery_task_id = None
    job.update_columns("celery_task_id")

    with _enqueue_returns(None, True):
        job.submit()

    shown = CosmonautJob(job_id=job.job_id)
    assert shown.get_status() == JOB_STATUS_FAILED
    assert f"Cannot start job {job.job_id}." in shown.get_logs()


def test_a_raising_enqueue_shows_failed_with_the_reason_in_the_job_log(running_job):
    job = CosmonautJob(job_id=running_job.job_id)
    set_run_columns(job.job_id, status=JOB_STATUS_PENDING)
    job.model.celery_task_id = None
    job.update_columns("celery_task_id")

    with (
        mock.patch(
            "cosmonaut_app.cosmonaut_job.submit_routing_job",
            side_effect=ConnectionError("broker unreachable"),
        ),
        pytest.raises(ConnectionError),
    ):
        job.submit()

    shown = CosmonautJob(job_id=job.job_id)
    assert shown.get_status() == JOB_STATUS_FAILED
    assert f"Cannot start job {job.job_id}." in shown.get_logs()


@pytest.mark.parametrize("finished_status", [JOB_STATUS_FAILED, JOB_STATUS_COMPLETED])
def test_a_restart_of_a_finished_job_revokes_no_task(
    running_job, route_computation, finished_status
):
    job_id = running_job.job_id
    set_run_columns(job_id, status=finished_status)

    with _revoking_must_not_happen(), _enqueue_returns("task-of-the-restart", False):
        route_computation.restart_computation(1, job_id)

    assert CosmonautJob(job_id=job_id).get_status() == JOB_STATUS_RUNNING


def test_a_resubmit_queues_the_run_without_the_last_runs_heartbeat(running_job):
    """The run claims only a RUNNING row without a heartbeat; an old heartbeat
    left by the last run would get the new run dropped."""
    job_id = running_job.job_id
    _give_the_row_a_heartbeat(job_id)
    set_run_columns(job_id, status=JOB_STATUS_FAILED)

    with _enqueue_returns("task-of-the-resubmit", False):
        CosmonautJob(job_id=job_id).submit()

    row = DataBaseManager.get_job_columns(job_id)
    assert row["status"] == JOB_STATUS_RUNNING
    assert row["heartbeat_at"] is None


def test_a_resubmit_of_a_notified_job_lets_the_next_end_mail_through(running_job):
    """notified_end belongs to the run: the end mail of the first run must not
    silence the end mail of a restart."""
    job_id = running_job.job_id
    running_job.model.notified_end = True
    running_job.update_columns("notified_end")
    set_run_columns(job_id, status=JOB_STATUS_COMPLETED)

    with _enqueue_returns("task-of-the-restart", False):
        job = CosmonautJob(job_id=job_id)
        job.reset()
        job.submit()

    assert DataBaseManager.get_job_columns(job_id)["notified_end"] is False


def test_a_reset_keeps_the_job_submitted_so_cleanup_keeps_its_retention(running_job):
    """Unsubmitted jobs are deleted 2 days after start_date: a reset must not
    put an old job back under that rule."""
    job_id = running_job.job_id

    CosmonautJob(job_id=job_id).reset()

    assert DataBaseManager.get_job_columns(job_id)["submitted"] is True


def test_a_reset_leaves_the_job_pending_without_a_heartbeat(running_job):
    job_id = running_job.job_id
    _give_the_row_a_heartbeat(job_id)

    CosmonautJob(job_id=job_id).reset()

    row = DataBaseManager.get_job_columns(job_id)
    assert row["status"] == JOB_STATUS_PENDING
    assert row["heartbeat_at"] is None


def test_the_queued_delivery_of_a_cancelled_job_is_dropped_without_a_mail(
    running_job,
):
    job_id = running_job.job_id
    job = CosmonautJob(job_id=job_id)
    with _enqueue_returns("task-of-the-cancelled-run", False):
        job.submit()
    job.cancel()

    with mock.patch("cosmonaut_app.tasks.routing_tasks.send_mail") as send_mail:
        process_routing_job(None, job_id)

    send_mail.assert_not_called()
    row = DataBaseManager.get_job_columns(job_id)
    assert row["status"] == JOB_STATUS_FAILED
    assert row["notified_end"] is False
    assert CANCELLED_MESSAGE in job_log.read(job_id)


def test_saving_a_job_loaded_before_a_heartbeat_keeps_the_runs_heartbeat(
    running_job,
):
    """The heartbeat belongs to the run: a web save of a job loaded earlier
    must not put an older (here: no) heartbeat back over it (ADR 0004)."""
    job_id = running_job.job_id
    loaded_before = CosmonautJob(job_id=job_id)
    _give_the_row_a_heartbeat(job_id)

    loaded_before.save()

    assert DataBaseManager.get_job_columns(job_id)["heartbeat_at"] is not None


def test_opening_route_download_of_a_reset_job_does_not_move_it_to_stage_5(
    running_job, route_download
):
    """Stage 5 belongs to a COMPLETED job; a PENDING job at stage 5 has no page
    in the job management table's link."""
    job_id = running_job.job_id
    running_job.reset()

    # The page has no route to show for a reset job; only the stage matters here.
    with contextlib.suppress(FileNotFoundError):
        route_download.layout(job_id)

    assert DataBaseManager.get_job_columns(job_id)["stage"] <= 4


def test_opening_route_download_of_a_completed_job_marks_stage_5(
    running_job, route_download
):
    job_id = running_job.job_id
    set_run_columns(job_id, status=JOB_STATUS_COMPLETED)

    with contextlib.suppress(FileNotFoundError):
        route_download.layout(job_id)

    assert DataBaseManager.get_job_columns(job_id)["stage"] == 5


def test_a_submit_returns_whether_it_queued_a_run_and_a_second_one_enqueues_nothing(
    running_job,
):
    job_id = running_job.job_id
    set_run_columns(job_id, status=JOB_STATUS_PENDING, submitted=False)

    with _enqueue_returns("task-of-the-first", False) as enqueue:
        first = CosmonautJob(job_id=job_id).submit()
        second = CosmonautJob(job_id=job_id).submit()

    assert (first, second) == (True, False)
    assert enqueue.call_count == 1
    row = DataBaseManager.get_job_columns(job_id)
    assert row["status"] == JOB_STATUS_RUNNING
    assert row["submitted"] is True
    assert row["celery_task_id"] == "task-of-the-first"


def test_a_submit_that_lost_the_guard_changes_nothing_in_the_row(running_job):
    """The row is RUNNING (a run that was queued by another tab): the loser must
    not clear the flag that run's end mail relies on, nor replace its task id."""
    job_id = running_job.job_id
    running_job.model.notified_end = True
    running_job.update_columns("notified_end")

    with _enqueue_returns("task-of-the-loser", False) as enqueue:
        submitted = CosmonautJob(job_id=job_id).submit()

    assert submitted is False
    enqueue.assert_not_called()
    row = DataBaseManager.get_job_columns(job_id)
    assert row["notified_end"] is True
    assert row["celery_task_id"] == "task-of-a-test"
    assert row["status"] == JOB_STATUS_RUNNING


@pytest.mark.parametrize("failing_step", ["work_dir", "save"])
def test_a_storage_error_after_the_guard_ends_the_job_failed(running_job, failing_step):
    """Nothing recovers a queued run no message will ever claim, so whatever
    fails between the guard and the enqueue must end the job FAILED."""
    job_id = running_job.job_id
    set_run_columns(job_id, status=JOB_STATUS_PENDING)

    with (
        mock.patch.object(
            job_persistence, failing_step, side_effect=ObjectStorageError("down")
        ),
        _enqueue_returns("never", False) as enqueue,
        pytest.raises(ObjectStorageError),
    ):
        CosmonautJob(job_id=job_id).submit()

    enqueue.assert_not_called()
    shown = CosmonautJob(job_id=job_id)
    assert shown.get_status() == JOB_STATUS_FAILED
    assert f"Cannot start job {job_id}." in shown.get_logs()


def test_a_failed_enqueue_does_not_fail_a_run_a_worker_already_claimed(running_job):
    job_id = running_job.job_id
    set_run_columns(job_id, status=JOB_STATUS_PENDING)

    def worker_claims_then_reports_failure(job):
        set_run_columns(job.model.job_id, heartbeat_at=func.now(), run_id=uuid.uuid4())
        return None, True

    with mock.patch(
        "cosmonaut_app.cosmonaut_job.submit_routing_job",
        side_effect=worker_claims_then_reports_failure,
    ):
        CosmonautJob(job_id=job_id).submit()

    assert DataBaseManager.get_job_columns(job_id)["status"] == JOB_STATUS_RUNNING


def test_a_cancel_of_a_running_job_revokes_its_task_and_ends_it_failed(running_job):
    job_id = running_job.job_id

    with mock.patch(
        "cosmo_ecosystem.background_job_manager.background_job_manager.revoke_job"
    ) as revoke:
        cancelled = CosmonautJob(job_id=job_id).cancel()

    assert cancelled is True
    revoke.assert_called_once_with("task-of-a-test", terminate=True)
    assert DataBaseManager.get_job_columns(job_id)["status"] == JOB_STATUS_FAILED


def test_a_cancel_of_a_job_that_just_completed_keeps_it_completed(running_job):
    """The run wrote COMPLETED a moment before the click reached the row."""
    job_id = running_job.job_id
    stale_view = CosmonautJob(job_id=job_id)
    set_run_columns(job_id, status=JOB_STATUS_COMPLETED)

    with mock.patch(
        "cosmo_ecosystem.background_job_manager.background_job_manager.revoke_job"
    ):
        cancelled = stale_view.cancel()

    assert cancelled is False
    assert DataBaseManager.get_job_columns(job_id)["status"] == JOB_STATUS_COMPLETED
    assert CANCELLED_MESSAGE not in job_log.read(job_id)


def test_a_reset_of_a_job_whose_run_was_queued_meanwhile_is_refused_and_changes_nothing(
    running_job,
):
    """The job object saw a finished job; another tab queued a run since."""
    job_id = running_job.job_id
    set_run_columns(job_id, status=JOB_STATUS_FAILED)
    stale_view = CosmonautJob(job_id=job_id)
    set_run_columns(job_id, status=JOB_STATUS_RUNNING)
    _log_to_job_log(job_id, "a line of the live run")

    reset = stale_view.reset()

    assert reset is False
    assert DataBaseManager.get_job_columns(job_id)["status"] == JOB_STATUS_RUNNING
    assert "a line of the live run" in job_log.read(job_id)
