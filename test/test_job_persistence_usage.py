"""Test that COSMONAUT's job class uses the framework's job persistence.

Runs against real Postgres and object storage. Outcomes only: rclone call
counts, files present locally and remotely, what a route serves.
"""

import base64
import importlib
import os
import shutil
from unittest import mock

import dash
import pytest
from cosmo_ecosystem import job_persistence, object_storage_manager
from cosmo_ecosystem.config import (
    JOB_WORK_DIR_TEMPLATE,
    OBJECT_STORAGE_BUCKET,
    OBJECT_STORAGE_REMOTE_NAME,
)
from cosmo_ecosystem.object_storage_manager import (
    delete_directory_from_storage,
    get_remote_files,
    save_files,
)
from sensor_routing.constants import MEMBERSHIP_FILENAME, PREDICTOR_FILENAME

from cosmonaut_app.constants.general import (
    GPX_FILE,
    JOB_STATUS_RUNNING,
    ROUTE_OPTIONS_FILE,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.files_route import serve_files


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


@pytest.fixture(scope="module")
def pollers():
    """Return the three status poll callbacks as plain functions.

    Page modules call ``register_page`` at import, which needs a Dash app with
    pages enabled to exist first, so they are imported here rather than at the
    top of the module (a deliberate departure from the top-level import rule).
    """
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return [
        importlib.import_module(
            "cosmonaut_app.pages.data_upload"
        ).poll_street_processing,
        importlib.import_module(
            "cosmonaut_app.pages.street_selection"
        ).poll_street_processing_status,
        importlib.import_module("cosmonaut_app.pages.route_computation").update_status,
    ]


@pytest.fixture
def job():
    """Yield a saved job and remove everything it left behind."""
    job = CosmonautJob()
    yield job
    job_id = job.model.job_id
    delete_directory_from_storage(job_id)
    shutil.rmtree(JOB_WORK_DIR_TEMPLATE.format(job_id=job_id), ignore_errors=True)
    if DataBaseManager.check_existence(job_id):
        DataBaseManager.delete_job(job_id)


def _remote_files(job_id):
    """List the objects stored below job_id's remote prefix."""
    return get_remote_files(
        f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{job_id}"
    )


def _write(job, name, content):
    """Write content to name in job's work dir."""
    with open(os.path.join(job.working_dir, name), "w") as f:
        f.write(content)


def _stored(job_id, name):
    """Return the content of name as object storage holds it."""
    shutil.rmtree(job_persistence.local_dir(job_id))
    with open(os.path.join(job_persistence.work_dir(job_id), name)) as f:
        return f.read()


def _data_url(path):
    """Return path's content as the data URL a dcc.Upload delivers."""
    with open(path, "rb") as f:
        return "data:text/csv;base64," + base64.b64encode(f.read()).decode()


def _upload_membership(job, membership_file_path, predictor_file_path):
    job.upload_membership("memberships.csv", _data_url(membership_file_path), 25832)


def _upload_predictor(job, membership_file_path, predictor_file_path):
    job.upload_predictor(_data_url(predictor_file_path))


def _submit(job, membership_file_path, predictor_file_path):
    with mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.submit_routing_job",
        return_value=("task", False),
    ):
        job.submit()


def _celery_says(status):
    """Patch the Celery state lookup the pollers use."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.get_job_status",
        return_value={"status": status},
    )


def test_loading_a_job_makes_no_rclone_calls(job, rclone_calls):
    rclone_calls.clear()

    CosmonautJob(job_id=job.model.job_id)

    assert rclone_calls == []


def test_the_status_pollers_make_no_rclone_calls(job, rclone_calls, pollers):
    job_id = job.model.job_id
    job.model.status = JOB_STATUS_RUNNING
    job.model.celery_task_id = "task"
    job.model.membership_upload["street_processing"] = "task"
    job.save()
    rclone_calls.clear()

    poll_street_processing, poll_street_processing_status, update_status = pollers
    with _celery_says("SUCCESS"):
        poll_street_processing(1, job_id)
        poll_street_processing_status(1, f"/job/{job_id}/street-selection")
        update_status(1, None, job_id)

    assert rclone_calls == []
    assert DataBaseManager.get_job_columns(job_id)["status"] == "COMPLETED"


def test_a_served_gpx_is_the_one_in_object_storage(job):
    """The pod serving a download may hold an older copy than the one stored."""
    job_id = job.model.job_id
    _write(job, GPX_FILE, "fresh")
    save_files(job_id)
    _write(job, GPX_FILE, "stale")
    app = dash.Dash(__name__)
    app.layout = dash.html.Div()
    serve_files(app)

    response = app.server.test_client().get(f"/download/{job_id}/{GPX_FILE}")

    assert response.data == b"fresh"


def test_deleting_the_membership_removes_it_from_object_storage(job):
    job_id = job.model.job_id
    _write(job, MEMBERSHIP_FILENAME, "x,y\n")
    _write(job, PREDICTOR_FILENAME, "x,y\n")
    job.save()
    assert {MEMBERSHIP_FILENAME, PREDICTOR_FILENAME} <= _remote_files(job_id)

    job.delete_membership()

    remote = _remote_files(job_id)
    assert MEMBERSHIP_FILENAME not in remote
    assert PREDICTOR_FILENAME not in remote
    assert not os.path.exists(os.path.join(job.working_dir, MEMBERSHIP_FILENAME))


def test_deleting_the_predictor_removes_it_from_object_storage(job):
    job_id = job.model.job_id
    _write(job, MEMBERSHIP_FILENAME, "x,y\n")
    _write(job, PREDICTOR_FILENAME, "x,y\n")
    job.save()

    job.delete_predictor()

    remote = _remote_files(job_id)
    assert PREDICTOR_FILENAME not in remote
    assert MEMBERSHIP_FILENAME in remote


@pytest.mark.parametrize(
    "modify", [_upload_membership, _upload_predictor, _submit], ids=lambda f: f.__name__
)
def test_a_web_modification_keeps_a_newer_stored_file(
    job, modify, membership_file_path, predictor_file_path
):
    """A pod with an outdated copy must not push it over the stored one."""
    job_id = job.model.job_id
    _upload_membership(job, membership_file_path, predictor_file_path)
    _write(job, ROUTE_OPTIONS_FILE, "fresh")
    save_files(job_id)
    _write(job, ROUTE_OPTIONS_FILE, "stale")

    modify(CosmonautJob(job_id=job_id), membership_file_path, predictor_file_path)

    assert _stored(job_id, ROUTE_OPTIONS_FILE) == "fresh"


@pytest.mark.parametrize(
    "path", ["/pictures/{}/plot.png", "/download/{}.zip", f"/download/{{}}/{GPX_FILE}"]
)
def test_a_file_route_answers_404_for_an_unknown_job(path):
    app = dash.Dash(__name__)
    app.layout = dash.html.Div()
    serve_files(app)

    response = app.server.test_client().get(path.format("nosuchjob"))

    assert response.status_code == 404
