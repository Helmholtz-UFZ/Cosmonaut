"""Test upload task retry logic for transient Overpass errors."""

import unittest.mock as mock

import pandas as pd
import pytest
import requests.exceptions
from cosmo_ecosystem import job_persistence
from cosmo_ecosystem.object_storage_manager import ObjectStorageError

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager


def _create_dummy_classification_data():
    """Create a dummy classification DataFrame for testing."""
    return pd.DataFrame(
        {
            "Latitude": [50.0, 50.1, 50.05],
            "Longitude": [10.0, 10.1, 10.05],
        }
    )


def _http_error(status_code):
    """Build an HTTPError carrying a real Response.

    A real requests.Response is falsy for any status >= 400 (Response.__bool__
    returns response.ok), unlike a MagicMock (always truthy). Using the real
    object is what makes these tests guard the `e.response is not None` retry
    condition instead of silently passing.
    """
    response = requests.models.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


def test_process_upload_task_retries_on_connection_error():
    """Test that process_upload_task retries on transient network errors."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    job = CosmonautJob()
    job.save()
    job_id = job.model.job_id

    task_mock = mock.MagicMock()
    task_mock.request.retries = 0

    with (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks._transform_csv",
            return_value=_create_dummy_classification_data(),
        ),
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=requests.exceptions.ConnectionError("Connection failed"),
        ),
    ):
        process_upload_task(task_mock, job_id, 4326)

    task_mock.retry.assert_called_once()
    call_kwargs = task_mock.retry.call_args[1]
    assert call_kwargs["countdown"] == 5
    assert call_kwargs["max_retries"] == 3


def test_process_upload_task_retries_on_timeout():
    """Test that process_upload_task retries on timeout errors."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    job = CosmonautJob()
    job.save()
    job_id = job.model.job_id

    task_mock = mock.MagicMock()
    task_mock.request.retries = 1

    with (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks._transform_csv",
            return_value=_create_dummy_classification_data(),
        ),
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=requests.exceptions.Timeout("Request timed out"),
        ),
    ):
        process_upload_task(task_mock, job_id, 4326)

    task_mock.retry.assert_called_once()
    call_kwargs = task_mock.retry.call_args[1]
    assert call_kwargs["countdown"] == 10
    assert call_kwargs["max_retries"] == 3


def test_process_upload_task_retries_on_http_429():
    """Test that process_upload_task retries on HTTP 429 (rate limit)."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    job = CosmonautJob()
    job.save()
    job_id = job.model.job_id

    task_mock = mock.MagicMock()
    task_mock.request.retries = 0

    with (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks._transform_csv",
            return_value=_create_dummy_classification_data(),
        ),
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=_http_error(429),
        ),
    ):
        process_upload_task(task_mock, job_id, 4326)

    task_mock.retry.assert_called_once()


def test_process_upload_task_retries_on_http_503():
    """Test that process_upload_task retries on HTTP 503 (service unavailable)."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    job = CosmonautJob()
    job.save()
    job_id = job.model.job_id

    task_mock = mock.MagicMock()
    task_mock.request.retries = 2

    with (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks._transform_csv",
            return_value=_create_dummy_classification_data(),
        ),
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=_http_error(503),
        ),
    ):
        process_upload_task(task_mock, job_id, 4326)

    task_mock.retry.assert_called_once()
    call_kwargs = task_mock.retry.call_args[1]
    assert call_kwargs["countdown"] == 20


def test_process_upload_task_does_not_retry_on_non_transient_http_error():
    """Test that process_upload_task does not retry on non-transient HTTP errors."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    job = CosmonautJob()
    job.save()
    job_id = job.model.job_id

    task_mock = mock.MagicMock()
    task_mock.request.retries = 0

    with (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks._transform_csv",
            return_value=_create_dummy_classification_data(),
        ),
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=_http_error(404),
        ),
    ):
        try:
            process_upload_task(task_mock, job_id, 4326)
        except requests.exceptions.HTTPError:
            pass

    task_mock.retry.assert_not_called()
    job_updated = CosmonautJob(job_id=job_id)
    assert job_updated.model.membership_upload["street_processing"] == "FAILED"


@pytest.fixture
def saved_job():
    """Yield a saved job; remove it afterwards."""
    job = CosmonautJob()
    job.save()
    yield job
    job_persistence.delete_job(job.job_id)


def _download_succeeds():
    """Patch the OSM query and the download checksum to succeed."""
    return (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks._transform_csv",
            return_value=_create_dummy_classification_data(),
        ),
        mock.patch("cosmonaut_app.tasks.upload_tasks.file_sha256", return_value="abc"),
    )


def test_a_finished_download_keeps_what_the_user_changed_meanwhile(saved_job):
    """The task owns the street processing state, not the rest of the row."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    def user_changes_the_email_during_the_download(*_args, **_kwargs):
        other = CosmonautJob(job_id=saved_job.job_id)
        other.model.email = "changed.meanwhile@ufz.de"
        other.update_columns("email")

    transform, sha = _download_succeeds()
    with (
        transform,
        sha,
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=user_changes_the_email_during_the_download,
        ),
    ):
        process_upload_task(mock.MagicMock(), saved_job.job_id, 4326)

    row = DataBaseManager.get_job_columns(saved_job.job_id)
    assert row["email"] == "changed.meanwhile@ufz.de"
    assert row["membership_upload"]["street_processing"] == "COMPLETED"
    assert row["membership_upload"]["download_sha256"] == "abc"


def test_exhausted_retries_end_failed_and_notify_the_maintainer(saved_job):
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    task_mock = mock.MagicMock()
    task_mock.request.retries = 3
    # Celery's retry re-raises the exception once max_retries is exhausted.
    task_mock.retry.side_effect = requests.exceptions.ConnectionError("down")

    transform, _sha = _download_succeeds()
    with (
        transform,
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=requests.exceptions.ConnectionError("down"),
        ),
        mock.patch("cosmonaut_app.tasks.upload_tasks.send_mail") as send_mail,
        pytest.raises(requests.exceptions.ConnectionError),
    ):
        process_upload_task(task_mock, saved_job.job_id, 4326)

    row = DataBaseManager.get_job_columns(saved_job.job_id)
    assert row["membership_upload"]["street_processing"] == "FAILED"
    send_mail.assert_called_once()


def test_a_failing_work_dir_pull_ends_failed_and_notifies_the_maintainer(saved_job):
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    with (
        mock.patch(
            "cosmonaut_app.tasks.upload_tasks.job_persistence.work_dir",
            side_effect=ObjectStorageError("storage down"),
        ),
        mock.patch("cosmonaut_app.tasks.upload_tasks.send_mail") as send_mail,
        pytest.raises(ObjectStorageError),
    ):
        process_upload_task(mock.MagicMock(), saved_job.job_id, 4326)

    row = DataBaseManager.get_job_columns(saved_job.job_id)
    assert row["membership_upload"]["street_processing"] == "FAILED"
    send_mail.assert_called_once()


def test_a_job_deleted_during_the_download_does_not_mask_the_error(saved_job):
    """Persisting FAILED fails (no row left), the maintainer still hears of the
    original error, which is the one that reaches Celery."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    def delete_the_job_then_fail(*_args, **_kwargs):
        job_persistence.delete_job(saved_job.job_id)
        raise RuntimeError("the original error")

    transform, _sha = _download_succeeds()
    with (
        transform,
        mock.patch(
            "cosmonaut_app.osm.OsmDownloader.run_osm_query",
            side_effect=delete_the_job_then_fail,
        ),
        mock.patch("cosmonaut_app.tasks.upload_tasks.send_mail") as send_mail,
        pytest.raises(RuntimeError, match="the original error"),
    ):
        process_upload_task(mock.MagicMock(), saved_job.job_id, 4326)

    send_mail.assert_called_once()
