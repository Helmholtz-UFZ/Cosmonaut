"""Test upload task retry logic for transient Overpass errors."""

import unittest.mock as mock

import pandas as pd
import requests.exceptions
import urllib3.exceptions

from cosmonaut_app.cosmonaut_job import CosmonautJob


def _create_dummy_classification_data():
    """Create a dummy classification DataFrame for testing."""
    return pd.DataFrame({
        "Latitude": [50.0, 50.1, 50.05],
        "Longitude": [10.0, 10.1, 10.05],
    })


def test_process_upload_task_retries_on_connection_error():
    """Test that process_upload_task retries on transient network errors."""
    from cosmonaut_app.tasks.upload_tasks import process_upload_task

    job = CosmonautJob()
    job.save()
    job_id = job.model.job_id

    task_mock = mock.MagicMock()
    task_mock.request.retries = 0

    with mock.patch(
        "cosmonaut_app.tasks.upload_tasks._transform_csv",
        return_value=_create_dummy_classification_data(),
    ), mock.patch(
        "cosmonaut_app.osm_downloader.OsmDownloader.run_osm_query",
        side_effect=requests.exceptions.ConnectionError("Connection failed"),
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

    with mock.patch(
        "cosmonaut_app.tasks.upload_tasks._transform_csv",
        return_value=_create_dummy_classification_data(),
    ), mock.patch(
        "cosmonaut_app.osm_downloader.OsmDownloader.run_osm_query",
        side_effect=requests.exceptions.Timeout("Request timed out"),
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

    response = mock.MagicMock()
    response.status_code = 429

    with mock.patch(
        "cosmonaut_app.tasks.upload_tasks._transform_csv",
        return_value=_create_dummy_classification_data(),
    ), mock.patch(
        "cosmonaut_app.osm_downloader.OsmDownloader.run_osm_query",
        side_effect=requests.exceptions.HTTPError(response=response),
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

    response = mock.MagicMock()
    response.status_code = 503

    with mock.patch(
        "cosmonaut_app.tasks.upload_tasks._transform_csv",
        return_value=_create_dummy_classification_data(),
    ), mock.patch(
        "cosmonaut_app.osm_downloader.OsmDownloader.run_osm_query",
        side_effect=requests.exceptions.HTTPError(response=response),
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

    response = mock.MagicMock()
    response.status_code = 404

    with mock.patch(
        "cosmonaut_app.tasks.upload_tasks._transform_csv",
        return_value=_create_dummy_classification_data(),
    ), mock.patch(
        "cosmonaut_app.osm_downloader.OsmDownloader.run_osm_query",
        side_effect=requests.exceptions.HTTPError(response=response),
    ):
        try:
            process_upload_task(task_mock, job_id, 4326)
        except requests.exceptions.HTTPError:
            pass

    task_mock.retry.assert_not_called()
    job_updated = CosmonautJob(job_id=job_id)
    assert job_updated.model.membership_upload["street_processing"] == "FAILED"
