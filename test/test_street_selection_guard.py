"""Test that the street edit callbacks leave a job alone once it is not PENDING.

A RUNNING, COMPLETED or FAILED job's street edits are the input of its run:
a stale tab (or a bookmark) must not change them. Runs against real Postgres and
object storage; calls the callbacks the way Dash does, with the page's pathname.
"""

import importlib

import dash
import pytest
from dash.exceptions import PreventUpdate

from cosmonaut_app.constants.general import JOB_STATUS_PENDING, JOB_STATUS_RUNNING
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.error_handling import JobNotPending
from cosmonaut_app.street_selector import StreetSelector
from test.help_functions_tests import remove_job, set_run_columns

_REMOVED_ROADS = [1, 2, 3]


@pytest.fixture(scope="module")
def street_selection():
    """Return the street selection page module (imported like route_computation)."""
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("cosmonaut_app.pages.street_selection")


@pytest.fixture
def running_job_with_removed_roads():
    """Yield a RUNNING job whose street edits removed three roads."""
    job = CosmonautJob()
    job.model.street_edits = {"removed_roads": _REMOVED_ROADS, "keep_largest": True}
    job.save()
    set_run_columns(job.job_id, status=JOB_STATUS_RUNNING)
    yield job
    remove_job(job.job_id)


def _pathname(job):
    return f"/job/{job.job_id}/street-selection"


def _street_edits(job):
    return DataBaseManager.get_job_columns(job.job_id)["street_edits"]


def test_reset_edits_does_nothing_for_a_job_that_is_not_pending(
    street_selection, running_job_with_removed_roads
):
    job = running_job_with_removed_roads

    with pytest.raises(PreventUpdate):
        street_selection.reset_edits(1, _pathname(job), 0)

    assert _street_edits(job)["removed_roads"] == _REMOVED_ROADS


def test_restore_single_road_does_nothing_for_a_job_that_is_not_pending(
    street_selection, running_job_with_removed_roads
):
    job = running_job_with_removed_roads

    with pytest.raises(PreventUpdate):
        street_selection.restore_single_road([1], _pathname(job), 0)

    assert _street_edits(job)["removed_roads"] == _REMOVED_ROADS


def test_clear_all_removed_roads_does_nothing_for_a_job_that_is_not_pending(
    street_selection, running_job_with_removed_roads
):
    job = running_job_with_removed_roads

    with pytest.raises(PreventUpdate):
        street_selection.clear_all_removed_roads(1, _pathname(job), 0)

    assert _street_edits(job)["removed_roads"] == _REMOVED_ROADS


def test_an_edit_from_a_stale_tab_does_not_change_the_street_edits_of_a_running_job(
    running_job_with_removed_roads,
):
    """The tab loaded the job while it was PENDING; the guard in the page passed,
    and the run started before the write. The row refuses it."""
    job = running_job_with_removed_roads
    set_run_columns(job.job_id, status=JOB_STATUS_PENDING)
    stale_view = CosmonautJob(job_id=job.job_id)
    set_run_columns(job.job_id, status=JOB_STATUS_RUNNING)

    with pytest.raises(JobNotPending):
        StreetSelector(stale_view).remove_roads([4])

    assert _street_edits(job)["removed_roads"] == _REMOVED_ROADS


def test_a_routing_parameter_write_from_a_stale_tab_leaves_a_running_job_alone(
    running_job_with_removed_roads,
):
    job = running_job_with_removed_roads
    stored = DataBaseManager.get_job_columns(job.job_id)["config"]["time_limit"]
    stale_view = CosmonautJob(job_id=job.job_id)
    stale_view.model.time_limit = stored + 1

    applied = stale_view.update_input("time_limit")

    assert applied is False
    row = DataBaseManager.get_job_columns(job.job_id)
    assert row["config"]["time_limit"] == stored
    assert row["status"] == JOB_STATUS_RUNNING


def test_a_routing_parameter_write_lands_while_the_job_is_pending(
    running_job_with_removed_roads,
):
    job = running_job_with_removed_roads
    set_run_columns(job.job_id, status=JOB_STATUS_PENDING)
    stale_view = CosmonautJob(job_id=job.job_id)
    new_limit = stale_view.model.time_limit + 1
    stale_view.model.time_limit = new_limit

    applied = stale_view.update_input("time_limit")

    assert applied is True
    config = DataBaseManager.get_job_columns(job.job_id)["config"]
    assert config["time_limit"] == new_limit
