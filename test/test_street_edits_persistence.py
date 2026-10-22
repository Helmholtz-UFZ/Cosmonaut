"""Test that street edits keep their intent in the job row (ticket 06).

The edited and projected GeoJSON are derived files: recomputed from the OSM
download and the row's intent when missing or stale. Runs against real
Postgres and object storage. Outcomes only: rclone and row-write counts, the
features in the files, what another pod sees.
"""

import hashlib
import importlib
import json
import os
import shutil

import dash
import pytest
from cosmo_ecosystem import job_persistence, object_storage_manager
from cosmo_ecosystem.config import (
    JOB_WORK_DIR_TEMPLATE,
    OBJECT_STORAGE_BUCKET,
    OBJECT_STORAGE_REMOTE_NAME,
)
from cosmo_ecosystem.db_manager import DbManager
from cosmo_ecosystem.object_storage_manager import (
    delete_directory_from_storage,
    get_remote_files,
)
from sensor_routing.constants import OSM_FILENAME

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    STREET_DERIVED_HASHES_FILE,
    STREET_EDITS_FILE,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.street_selector import StreetSelector
from test.help_functions_tests import another_pod_meanwhile

_ROAD_IDS = [1, 2, 3]


def _road(road_id):
    """Return a residential road feature a little east of the previous one."""
    lon = 12.37 + road_id * 0.001
    return {
        "type": "Feature",
        "id": road_id,
        "properties": {"highway": "residential", "osmid": road_id},
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, 51.34], [lon + 0.001, 51.34]],
        },
    }


@pytest.fixture
def rclone_calls(monkeypatch):
    """Count the rclone commands object_storage_manager runs."""
    calls = []
    real = object_storage_manager.run_rclone_with_retry

    def counting(params, *args, **kwargs):
        calls.append(params)
        return real(params, *args, **kwargs)

    monkeypatch.setattr(object_storage_manager, "run_rclone_with_retry", counting)
    return calls


@pytest.fixture
def row_writes(monkeypatch):
    """Count the writes to the jobs table (whole-row and column updates)."""
    writes = []
    real_add_entry = DbManager.add_entry.__func__
    real_update_column = DbManager.update_column.__func__

    def add_entry(cls, data):
        writes.append(sorted(data))
        return real_add_entry(cls, data)

    def update_column(cls, job_id, columns):
        writes.append(sorted(columns))
        return real_update_column(cls, job_id, columns)

    monkeypatch.setattr(DbManager, "add_entry", classmethod(add_entry))
    monkeypatch.setattr(DbManager, "update_column", classmethod(update_column))
    return writes


@pytest.fixture(scope="module")
def street_selection_layout():
    """Return the street selection page's layout function, as the app registers it.

    The layout builds links from ``dash.page_registry``, which only the app's
    own Dash instance fills. ``cosmonaut_app.app`` boots Dash and object storage
    at import, so it is imported here, as conftest's ``dash_app`` does, rather
    than at the top of the module (a deliberate departure from the top-level
    import rule).
    """
    importlib.import_module("cosmonaut_app.app")
    return dash.page_registry["pages.street_selection"]["layout"]


@pytest.fixture
def job():
    """Yield a job whose OSM download is stored and street processing done."""
    job = CosmonautJob()
    _store_download(job, _ROAD_IDS)
    yield job
    job_id = job.model.job_id
    delete_directory_from_storage(job_id)
    shutil.rmtree(JOB_WORK_DIR_TEMPLATE.format(job_id=job_id), ignore_errors=True)
    if DataBaseManager.check_existence(job_id):
        DataBaseManager.delete_job(job_id)


def _store_download(job, road_ids):
    """Store a new OSM download of road_ids, as the upload worker does."""
    job_persistence.work_dir(job.job_id)
    _write_json(
        job,
        OSM_DATA_DOWNLOAD_FILE,
        {"type": "FeatureCollection", "features": [_road(i) for i in road_ids]},
    )
    with open(os.path.join(job.working_dir, OSM_DATA_DOWNLOAD_FILE), "rb") as f:
        checksum = hashlib.sha256(f.read()).hexdigest()
    job.model.membership_upload["street_processing"] = "COMPLETED"
    job.model.membership_upload["download_sha256"] = checksum
    job.save()


def _write_json(job, name, data):
    with open(os.path.join(job.working_dir, name), "w") as f:
        json.dump(data, f)


def _road_ids(job, name):
    """Return the OSM ids of the roads in the job's local file name."""
    with open(os.path.join(job.working_dir, name)) as f:
        features = json.load(f)["features"]
    return sorted(feature["properties"]["osmid"] for feature in features)


def _remote_files(job_id):
    return get_remote_files(
        f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{job_id}"
    )


def _another_pod(job):
    """Drop the job's local work dir, as seen from a pod that never had it."""
    shutil.rmtree(job.working_dir)
    return CosmonautJob(job_id=job.model.job_id)


def test_an_edit_makes_no_rclone_call_and_one_row_write(job, rclone_calls, row_writes):
    selector = StreetSelector(CosmonautJob(job_id=job.model.job_id))
    rclone_calls.clear()
    row_writes.clear()

    selector.remove_roads([2])

    assert rclone_calls == []
    assert len(row_writes) == 1


def test_another_pod_sees_an_edit(job):
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])

    other = _another_pod(job)

    assert StreetSelector(other).removed_roads == [2]


def test_opening_street_selection_recomputes_missing_derived_files(
    job, street_selection_layout
):
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])
    other = _another_pod(job)

    street_selection_layout(other.model.job_id)

    assert _road_ids(other, OSM_DATA_EDITED_FILE) == [1, 3]


def test_opening_street_selection_recomputes_a_stale_derived_file(
    job, street_selection_layout
):
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])
    # Another pod restores road 2 and removes road 3: only the row changes here.
    intent = CosmonautJob(job_id=job.model.job_id).model.street_edits
    intent.removed_roads = [3]
    job_persistence.update_columns(
        job.model.job_id, {"street_edits": intent.model_dump(mode="json")}
    )

    street_selection_layout(job.model.job_id)

    assert _road_ids(job, OSM_DATA_EDITED_FILE) == [1, 2]


def test_submit_uploads_the_derived_files_and_the_worker_finds_them(job):
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])

    # What submit does before handing the job to Celery.
    CosmonautJob(job_id=job.model.job_id).save()

    assert OSM_DATA_EDITED_FILE in _remote_files(job.model.job_id)
    # The routing worker on another pod: pull, then make the routing input.
    worker_job = _another_pod(job)
    job_persistence.work_dir(worker_job.job_id)
    StreetSelector(worker_job).ensure_projected()
    assert _road_ids(worker_job, OSM_DATA_EDITED_FILE) == [1, 3]
    assert _road_ids(worker_job, OSM_FILENAME) == [1, 3]


def test_a_job_edited_before_the_row_held_the_intent_keeps_its_edits(
    job, street_selection_layout
):
    """A prod job whose edits are only in the legacy street_edits.json."""
    _write_json(
        job,
        STREET_EDITS_FILE,
        {
            "removed_roads": [3],
            "selected_road_tags": StreetSelector(job).selected_road_tags,
            "keep_largest": False,
        },
    )
    job.save()
    other = _another_pod(job)

    street_selection_layout(other.model.job_id)

    assert _road_ids(other, OSM_DATA_EDITED_FILE) == [1, 2]
    assert STREET_EDITS_FILE not in _remote_files(other.model.job_id)
    assert StreetSelector(_another_pod(other)).removed_roads == [3]


def test_deleting_the_membership_forgets_the_street_edits(job):
    """A new upload brings a new network; the old edits must not apply to it."""
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])
    CosmonautJob(job_id=job.model.job_id).save()

    CosmonautJob(job_id=job.model.job_id).delete_membership()

    assert StreetSelector(_another_pod(job)).removed_roads == []
    remote = _remote_files(job.model.job_id)
    assert OSM_DATA_EDITED_FILE not in remote
    assert STREET_DERIVED_HASHES_FILE not in remote


def test_an_edited_network_built_from_another_download_is_recomputed(
    job, street_selection_layout
):
    """Same intent, new download: the old derived file must not count as current."""
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])
    with another_pod_meanwhile(job) as other:
        other.delete_membership()
        _store_download(other, [1, 2, 3, 4])
        StreetSelector(CosmonautJob(job_id=other.model.job_id)).remove_roads([2])

    street_selection_layout(job.model.job_id)

    assert _road_ids(job, OSM_DATA_EDITED_FILE) == [1, 3, 4]


def test_an_edited_network_pulled_without_its_record_is_recomputed(
    job, street_selection_layout
):
    """A pull may replace the derived file but keep this pod's record of it."""
    # The upload worker stores an unedited network beside the download.
    _write_json(
        job,
        OSM_DATA_EDITED_FILE,
        {"type": "FeatureCollection", "features": [_road(i) for i in _ROAD_IDS]},
    )
    job.save()
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])

    street_selection_layout(job.model.job_id)

    assert _road_ids(job, OSM_DATA_EDITED_FILE) == [1, 3]


_VIEWPORT = [[51.33, 12.36], [51.35, 12.38]]


def _viewport_road_ids(job):
    """Return the ids of the roads the map shows for job on this pod."""
    selector = StreetSelector(CosmonautJob(job_id=job.model.job_id))
    return sorted(f["id"] for f in selector.viewport_fc(_VIEWPORT, 14)["features"])


def test_the_map_shows_edited_streets_on_a_pod_without_the_files(
    job, rclone_transfers
):
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])
    _another_pod(job)
    rclone_transfers.clear()

    first_view = _viewport_road_ids(job)
    pulls_on_first_view = len(rclone_transfers)
    rclone_transfers.clear()
    after_map_move = _viewport_road_ids(job)

    assert first_view == after_map_move == [1, 3]
    assert pulls_on_first_view == 1  # pull_file of the download
    assert rclone_transfers == []


def test_the_map_shows_no_streets_once_another_pod_deleted_the_membership(job):
    StreetSelector(CosmonautJob(job_id=job.model.job_id)).remove_roads([2])
    with another_pod_meanwhile(job) as other:
        other.delete_membership()

    assert _viewport_road_ids(job) == []
