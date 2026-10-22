"""Test that the map's route and raster layers read the stored files (ticket 08).

The map callback runs on every navigation, on any pod. Runs against real
Postgres and object storage; outcomes only: what the map shows, and how many
rclone processes it starts.
"""

import json
import os
import shutil

import pytest
from cosmo_ecosystem import job_persistence
from cosmo_ecosystem.object_storage_manager import delete_directory_from_storage
from sensor_routing.constants import MEMBERSHIP_FILENAME, ROUTE_FILENAME

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    MEMBERSHIP_TIF,
    ROUTE_OPTIONS_FILE,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.map_utils import map_layer_data
from test.help_functions_tests import another_pod_meanwhile

# West to east, in the job's default EPSG 25832.
_ROUTE = [[620250, 5761250], [620500, 5761250], [620750, 5761250]]


@pytest.fixture
def job():
    """Yield a completed job with a membership raster and a reversed route."""
    job = CosmonautJob()
    job.model.membership_upload["file_name"] = MEMBERSHIP_FILENAME
    job.model.status = JOB_STATUS_COMPLETED
    _write(job, MEMBERSHIP_TIF, "raster")
    _write(job, ROUTE_FILENAME, json.dumps({"Path": _ROUTE}))
    _write(job, ROUTE_OPTIONS_FILE, json.dumps({"reversed": True}))
    job.save()
    yield job
    job_id = job.model.job_id
    delete_directory_from_storage(job_id)
    shutil.rmtree(job_persistence.local_dir(job_id), ignore_errors=True)
    if DataBaseManager.check_existence(job_id):
        DataBaseManager.delete_job(job_id)


def _write(job, name, content):
    with open(os.path.join(job.working_dir, name), "w") as f:
        f.write(content)


def _on_a_pod_without_the_files(job):
    shutil.rmtree(job.working_dir)
    return CosmonautJob(job_id=job.model.job_id)


def test_the_map_shows_the_stored_route_and_raster_on_a_pod_without_them(
    job, rclone_transfers
):
    other = _on_a_pod_without_the_files(job)
    rclone_transfers.clear()

    tile_url, positions = map_layer_data(other)

    assert tile_url != ""
    assert len(positions) == 3
    # Reversed: the route starts in the east.
    assert positions[0][1] > positions[-1][1]
    # One pull_file each for the raster, the route and its options.
    assert len(rclone_transfers) == 3


def test_the_map_shows_no_route_once_another_pod_reset_the_job(job):
    with another_pod_meanwhile(job) as other:
        other.reset()

    _tile_url, positions = map_layer_data(CosmonautJob(job_id=job.model.job_id))

    assert positions == []


def test_the_map_pulls_nothing_for_a_job_without_uploads(rclone_transfers):
    job = CosmonautJob()
    rclone_transfers.clear()
    try:
        assert map_layer_data(job) == ("", [])
        assert rclone_transfers == []
    finally:
        DataBaseManager.delete_job(job.model.job_id)
        delete_directory_from_storage(job.model.job_id)
        shutil.rmtree(job.working_dir, ignore_errors=True)
