"""Test that the street edit callbacks leave a job alone once it is not PENDING.

A RUNNING, COMPLETED or FAILED job's street edits are the input of its run:
a stale tab (or a bookmark) must not change them. Runs against real Postgres and
object storage; calls the callbacks the way Dash does, with the page's pathname.
"""

import importlib

import dash
import pytest
from cosmo_ecosystem import job_persistence
from dash.exceptions import PreventUpdate

from cosmonaut_app.constants.general import JOB_STATUS_RUNNING
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager

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
    job.model.status = JOB_STATUS_RUNNING
    job.model.street_edits = {"removed_roads": _REMOVED_ROADS, "keep_largest": True}
    job.save()
    yield job
    job_persistence.delete_job(job.job_id)


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
