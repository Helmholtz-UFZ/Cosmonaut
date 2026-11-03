"""Test that input and stage writes on an existing job are conditional in the row.

A page that loaded the job while it was PENDING can write after a run was queued
(a second tab, a stale view). The row decides (cosmo-ecosystem ADR 0005): input
writes apply only while PENDING, a stage only ever rises. Runs against real
Postgres and object storage; calls the callbacks the way Dash does.
"""

import base64
import contextlib
import importlib
from unittest import mock

import dash
import pytest
from cosmo_ecosystem import job_persistence
from dash._callback_context import context_value
from dash._utils import AttributeDict

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
)
from cosmonaut_app.constants.html_ids import NEXT_BUTTON_ROUTING_PARAMS_ID
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.error_handling import JobNotPending
from test.help_functions_tests import celery_says, remove_job, set_run_columns


def _page(name):
    """Return a page module; the pages call ``register_page`` at import, which
    needs a Dash app with pages enabled first (a deliberate departure from the
    top-level import rule)."""
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module(f"cosmonaut_app.pages.{name}")


@pytest.fixture
def job():
    """Yield a saved PENDING job; remove it afterwards."""
    job = CosmonautJob()
    yield job
    remove_job(job.job_id)


@pytest.fixture
def stale_view(job, membership_file_path):
    """Return the job as a page loaded it while PENDING, with the row RUNNING now.

    The job has a membership upload, as every job a run can start from has.
    """
    job.upload_membership("memberships.csv", _data_url(membership_file_path), 25832)
    view = CosmonautJob(job_id=job.job_id)
    set_run_columns(job.job_id, status=JOB_STATUS_RUNNING)
    return view


def _column(job, name):
    return DataBaseManager.get_job_columns(job.job_id)[name]


def _data_url(path):
    with open(path, "rb") as f:
        return "data:text/csv;base64," + base64.b64encode(f.read()).decode()


def test_the_email_of_a_running_job_is_not_changed_by_a_stale_user_info_tab(
    job, stale_view
):
    user_info = _page("user_info")
    before = _column(job, "email")

    with (
        mock.patch.object(user_info, "CosmonautJob", return_value=stale_view),
        mock.patch.object(user_info, "build_url_step"),
        pytest.raises(JobNotPending),
    ):
        user_info.go_to_upload_page(1, "someone@ufz.de", f"/job/{job.job_id}/user-info")

    assert _column(job, "email") == before


def test_the_email_of_a_pending_job_is_written_with_its_stage(job):
    user_info = _page("user_info")

    with mock.patch.object(user_info, "build_url_step"):
        user_info.go_to_upload_page(1, "someone@ufz.de", f"/job/{job.job_id}/user-info")

    assert _column(job, "email") == "someone@ufz.de"
    assert _column(job, "stage") == 1


def test_the_routing_parameters_of_a_running_job_are_not_changed_by_a_stale_tab(
    job, stale_view
):
    routing_params = _page("routing_params")
    stored = _column(job, "config")["time_limit"]
    inputs = {
        key: getattr(stale_view.model, key)
        for key in routing_params.form_factory.produce_callback_inputs()
    }
    inputs["time_limit"] = stored + 1
    context_value.set(
        AttributeDict(
            triggered_inputs=[
                {"prop_id": f"{NEXT_BUTTON_ROUTING_PARAMS_ID}.n_clicks", "value": 1}
            ]
        )
    )

    with (
        mock.patch.object(routing_params, "CosmonautJob", return_value=stale_view),
        pytest.raises(JobNotPending),
    ):
        routing_params.update_routing_params(job_id=job.job_id, input_next=1, **inputs)

    assert _column(job, "config")["time_limit"] == stored


@pytest.mark.parametrize(
    "upload",
    [
        lambda job, membership, predictor: job.upload_membership(
            "memberships.csv", _data_url(membership), 25833
        ),
        lambda job, membership, predictor: job.upload_predictor(_data_url(predictor)),
    ],
    ids=["membership", "predictor"],
)
def test_an_upload_from_a_stale_tab_does_not_change_a_running_job(
    job, stale_view, membership_file_path, predictor_file_path, upload
):
    before = _column(job, "membership_upload"), _column(job, "predictor_upload")

    with contextlib.suppress(JobNotPending):
        upload(stale_view, membership_file_path, predictor_file_path)

    assert (_column(job, "membership_upload"), _column(job, "predictor_upload")) == (
        before
    )
    assert _column(job, "status") == JOB_STATUS_RUNNING


def test_a_membership_upload_to_a_running_job_is_refused_before_it_deletes_files(
    job, stale_view, membership_file_path
):
    data_upload = _page("data_upload")

    with (
        mock.patch.object(job_persistence, "delete_files") as delete_files,
        pytest.raises(JobNotPending),
    ):
        data_upload._handle_membership_upload(
            _data_url(membership_file_path), "memberships.csv", job.job_id, 25832
        )

    delete_files.assert_not_called()


@pytest.mark.parametrize(
    ("row_stage", "raised_to", "expected"), [(4, 2, 4), (1, 3, 3), (3, 3, 3)]
)
def test_a_stage_only_ever_rises(job, row_stage, raised_to, expected):
    DataBaseManager.update_column(job.job_id, {"stage": row_stage})
    stale_view = CosmonautJob(job_id=job.job_id)
    stale_view.model.stage = 0

    stale_view.raise_stage(raised_to)

    assert _column(job, "stage") == expected


def test_opening_route_download_does_not_write_a_stale_row_over_another_tab(job):
    """The QR code takes a while; a column written meanwhile must survive."""
    route_download = _page("route_download")
    set_run_columns(job.job_id, status=JOB_STATUS_COMPLETED)

    def another_tab_writes_the_email_meanwhile():
        DataBaseManager.update_column(job.job_id, {"email": "other@ufz.de"})

    with (
        mock.patch.object(
            CosmonautJob,
            "create_qr_code_routing",
            side_effect=another_tab_writes_the_email_meanwhile,
        ),
        # The page's rendering is not under test: stop once the row is settled.
        mock.patch.object(
            route_download, "get_download_url", side_effect=FileNotFoundError
        ),
        contextlib.suppress(FileNotFoundError),
    ):
        route_download.layout(job.job_id)

    assert _column(job, "email") == "other@ufz.de"
    assert _column(job, "status") == JOB_STATUS_COMPLETED


def test_a_new_job_is_pending(job):
    assert _column(job, "status") == JOB_STATUS_PENDING


def _street_processing_task_running(job, task_id="upload-task"):
    """Make the row name an upload task that is still processing the streets."""
    upload = {**_column(job, "membership_upload"), "street_processing": task_id}
    DataBaseManager.update_column(job.job_id, {"membership_upload": upload})
    return task_id


def test_the_street_processing_poll_does_not_lower_a_stage_another_tab_raised(job):
    _street_processing_task_running(job)
    stale_view = CosmonautJob(job_id=job.job_id)
    DataBaseManager.update_column(job.job_id, {"stage": 4})

    with celery_says("SUCCESS"):
        assert stale_view.get_street_processing_status() == "COMPLETED"

    assert _column(job, "stage") == 4
    assert _column(job, "membership_upload")["street_processing"] == "COMPLETED"


def test_the_street_processing_poll_writes_only_the_street_processing_state(job):
    _street_processing_task_running(job)
    stale_view = CosmonautJob(job_id=job.job_id)
    upload = {**_column(job, "membership_upload"), "len": 689, "zoom": 13}
    DataBaseManager.update_column(job.job_id, {"membership_upload": upload})

    with celery_says("SUCCESS"):
        stale_view.get_street_processing_status()

    row_upload = _column(job, "membership_upload")
    assert (row_upload["len"], row_upload["zoom"]) == (689, 13)
    assert row_upload["street_processing"] == "COMPLETED"


def test_the_street_processing_poll_of_a_superseded_task_writes_nothing(job):
    _street_processing_task_running(job, "old-task")
    stale_view = CosmonautJob(job_id=job.job_id)
    _street_processing_task_running(job, "new-task")

    with celery_says("FAILURE"):
        stale_view.get_street_processing_status()

    assert _column(job, "membership_upload")["street_processing"] == "new-task"
