"""Test complete routing workflow from job creation to route download.

This test validates the end-to-end user journey:
1. Create a new job from the home page
2. Enter email on user info page
3. Upload a CSV file with member data
4. Navigate through street selection
5. Configure routing parameters
6. Start and wait for route computation
7. Verify the download URL is visible on the route download page
8. Verify email notification was sent (notified_end flag in DB)
9. Download work_dir zip and verify contents match expected file set
"""

import io
import logging
import os
import time
import zipfile

import pytest
from playwright.sync_api import expect

from cosmonaut_app.config import PORT
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID,
    EMAIL_INPUT_USER_INFO_ID,
    LOADING_OVERLAY_MODAL_SHARED_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    NEXT_BUTTON_ROUTE_COMPUTATION_ID,
    NEXT_BUTTON_ROUTING_PARAMS_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
    NEXT_BUTTON_USER_INFO_ID,
    PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    START_BUTTON_ROUTE_COMPUTATION_ID,
    START_JOB_BUTTON_HOME_ID,
)
from cosmonaut_app.db_manager import DataBaseManager
from test.help_functions_tests import check_all_errors

log = logging.getLogger(__name__)


def test_complete_routing_workflow(
    page,
    dash_app,
    celery_worker,
    membership_file_path,
    predictor_file_path,
    worker_log_path,
    osm_cache_patch,
) -> None:
    """Test the complete routing workflow from job creation to route download."""
    # === Home Page ===
    page.goto(f"http://localhost:{PORT}/")
    page.locator(f"#{START_JOB_BUTTON_HOME_ID}").click()
    check_all_errors(page)

    # === User Info Page ===
    email_input = page.locator(f"#{EMAIL_INPUT_USER_INFO_ID}")
    email_input.fill("test@ufz.de")
    expect(page.locator(f"#{NEXT_BUTTON_USER_INFO_ID}")).to_be_enabled(timeout=5000)
    page.locator(f"#{NEXT_BUTTON_USER_INFO_ID}").click()
    check_all_errors(page)

    # === Data Upload Page ===
    # Upload membership file
    page.locator(
        f"#{DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']"
    ).set_input_files(str(membership_file_path))
    # Upload predictor file (enabled after membership upload completes)
    expect(
        page.locator(f"#{PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']")
    ).to_be_enabled(timeout=120000)
    page.locator(
        f"#{PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']"
    ).set_input_files(str(predictor_file_path))
    expect(page.locator(f"#{NEXT_BUTTON_DATA_UPLOAD_ID}")).to_be_enabled(timeout=120000)
    # Wait for loading overlay to close — the predictor callback enables the button
    # but the overlay may still be visible (backdrop="static" intercepts clicks)
    expect(page.locator(f"#{LOADING_OVERLAY_MODAL_SHARED_ID}")).not_to_be_visible(
        timeout=10000
    )
    page.locator(f"#{NEXT_BUTTON_DATA_UPLOAD_ID}").click()
    check_all_errors(page)

    # === Street Selection Page ===
    # Wait for street processing (OSM download) to complete — the page polls
    # and reloads when done, enabling the next button.
    # If the OSM step fails (street_processing == "FAILED"), fail fast instead of
    # burning the full 300s timeout. Extract job_id from URL and poll DB.
    job_id = page.url.split("/job/")[1].split("/")[0]
    start_time = time.time()
    timeout_seconds = 300
    poll_interval = 2

    while time.time() - start_time < timeout_seconds:
        job_row = DataBaseManager.get_job_columns(job_id)
        street_processing = job_row["membership_upload"].get("street_processing")

        if street_processing == "FAILED":
            pytest.fail(
                "Street processing failed during upload. Check logs for details."
            )

        try:
            expect(page.locator(f"#{NEXT_BUTTON_STREET_SELECTION_ID}")).to_be_enabled(
                timeout=poll_interval * 1000
            )
            break
        except Exception:
            time.sleep(poll_interval)
    page.locator(f"#{NEXT_BUTTON_STREET_SELECTION_ID}").click()
    check_all_errors(page)

    # === Routing Parameters Page ===
    page.locator(f"#{NEXT_BUTTON_ROUTING_PARAMS_ID}").click()
    # Note: check_all_errors skipped here because route_computation page has polling
    # that prevents networkidle state from being reached

    # === Route Computation Page ===
    # Wait for the Start button to be visible and click it
    expect(page.locator(f"#{START_BUTTON_ROUTE_COMPUTATION_ID}")).to_be_visible(
        timeout=10000
    )
    page.locator(f"#{START_BUTTON_ROUTE_COMPUTATION_ID}").click()
    # Wait for computation to complete (Next button becomes enabled)
    expect(page.locator(f"#{NEXT_BUTTON_ROUTE_COMPUTATION_ID}")).to_be_enabled(
        timeout=240000
    )
    page.locator(f"#{NEXT_BUTTON_ROUTE_COMPUTATION_ID}").click()
    # Note: check_all_errors skipped here as we're navigating to route_download

    # === Route Download Page ===
    # Verify that the download URL is visible
    expect(page.locator(f"#{DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID}")).to_be_visible()
    check_all_errors(page)

    # === Verify email notification was sent ===
    # Poll rather than read once: the UI gate above is `status == COMPLETED`,
    # written by the worker's first job.save(). notified_end is written by a
    # *second* save inside _notify_user, which runs after it. Reading the row
    # immediately can land between the two — it passes on a fast machine and
    # fails on CI, which is what happened.
    job_row = DataBaseManager.get_job_columns(job_id)
    for _ in range(30):
        if job_row["notified_end"] is True:
            break
        time.sleep(1)
        job_row = DataBaseManager.get_job_columns(job_id)

    assert (
        job_row["email"] == "test@ufz.de"
    ), f"Expected email 'test@ufz.de' in DB, got '{job_row['email']}'"
    assert job_row["notified_end"] is True, (
        "Expected notified_end=True in DB after job completion — "
        "email notification was not recorded"
    )

    # Verify email notifications were logged by the worker
    worker_log = worker_log_path.read_text()
    assert (
        "Send mail about submitted job" in worker_log
    ), "Worker log missing submission email log"
    assert (
        "Send mail about finished job" in worker_log
    ), "Worker log missing finished email log"

    # === Download work_dir zip and verify contents ===
    download_link = page.locator("a[href*='/download/'][href$='.zip']")
    expect(download_link).to_be_visible(timeout=5000)
    download_href = download_link.get_attribute("href")

    with dash_app.server.test_client() as client:
        response = client.get(download_href)
        assert response.status_code == 200, f"Download failed: {response.status_code}"
        assert response.content_type == "application/zip"

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data) as zf:
            zip_file_names = sorted(zf.namelist())
            log.info(f"Zip file names: {zip_file_names}")

            # Verify zip matches work_dir on disk
            work_dir = os.path.join("cosmonaut_app/work_dir", job_id)
            disk_file_names = sorted(
                os.path.relpath(os.path.join(root, f), work_dir)
                for root, _, files in os.walk(work_dir)
                for f in files
            )
            log.info(f"Disk file names: {disk_file_names}")
            assert zip_file_names == disk_file_names, (
                f"Zip contents don't match work_dir.\n"
                f"Zip: {zip_file_names}\nDisk: {disk_file_names}"
            )

            # Verify file contents are identical
            for name in zip_file_names:
                with open(os.path.join(work_dir, name), "rb") as f:
                    disk_content = f.read()
                zip_content = zf.read(name)
                assert zip_content == disk_content, f"Content mismatch for {name}"

            expected_files = {
                "membership.tif",
                "memberships.csv",
                "osm_data_download.geojson",
                "osm_data_edited.geojson",
                "osm_data_transformed.geojson",
                "parameters.json",
                "points.csv",
                "predictors.csv",
                "qr_code.png",
                "route.gpx",
                "solution.json",
                "street_edits.json",
                "transient/bc_benefits_output.json",
                "transient/bc_top_benefits_output.json",
                "transient/econ_bc_benefits_output.json",
                "transient/econ_bc_top_benefits_output.json",
                "transient/econ_pf_output.json",
                "transient/econ_pm_output.json",
                "transient/initial_route.json",
                "transient/maxspeed_information.json",
                "transient/optimal_grid_cells_50_filtered_bbox.json",
                "transient/pf_output.json",
                "transient/pm_output.json",
                "transient/point_hull_collection.json",
                "transient/slow_coords.json",
                "worker.log",
            }
            assert set(zip_file_names) == expected_files, (
                f"Unexpected files in work_dir zip.\n"
                f"Zip: {sorted(zip_file_names)}\nExpected: {sorted(expected_files)}"
            )
