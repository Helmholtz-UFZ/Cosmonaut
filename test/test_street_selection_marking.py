"""Street-selection marking via map clicks (Playwright).

Regression test for the interactive marking flow: clicking a street on the
map must mark it (badge "Selected: 1"). Deliberately uses a HARD page load
of the street-selection URL (page.goto) instead of SPA navigation — that is
what happens after a browser refresh (e.g. following a dev hot-reload), and
it is the path where the map's client-side state (hideout dimmed flag,
current job id) is most easily left stale.

Streets render on a canvas (preferCanvas), so there are no per-feature DOM
nodes to click — the test locates a street by scanning a map screenshot for
the street color and clicks that viewport pixel.
"""

import io
import logging
import time

import pytest
from PIL import Image
from playwright.sync_api import expect

from test.help_functions_tests import check_all_errors
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    EMAIL_INPUT_USER_INFO_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MAP_LEGEND_COLLAPSE_SHARED_ID,
    MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID,
    NEXT_BUTTON_USER_INFO_ID,
    SELECTED_BADGE_STREET_SELECTION_ID,
    START_JOB_BUTTON_HOME_ID,
)
from cosmonaut_app.db_manager import DataBaseManager

log = logging.getLogger(__name__)


def _find_street_pixel(page):
    """Return viewport (x, y) of an unmarked street pixel, or None.

    Detects the street red (#d32f2f at editing opacity) while rejecting the
    pink-red motorway color of the OSM base tiles (its green channel is far
    higher).
    """
    map_box = page.locator(f"#{MAIN_MAP_COMPONENT_MAP_SHARED_ID}").bounding_box()
    shot = page.screenshot(clip=map_box)
    img = Image.open(io.BytesIO(shot)).convert("RGB")
    width, height = img.size
    pixels = img.load()
    for y in range(10, height - 10, 3):
        for x in range(10, width - 10, 3):
            r, g, b = pixels[x, y]
            if r > 150 and g < 90 and b < 90 and r - g > 80:
                return map_box["x"] + x, map_box["y"] + y
    return None


def _wait_for_street_pixel(page, timeout_seconds=30):
    """Poll until a street pixel is visible on the map."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        pixel = _find_street_pixel(page)
        if pixel is not None:
            return pixel
        time.sleep(1)
    return None


def _upload_membership_and_wait(page, membership_file_path):
    """Create a job, upload the membership file, wait for street processing.

    Returns the job_id. Stops after the OSM download completes — the
    predictor upload is not needed for street selection.
    """
    page.goto(f"http://localhost:{FLASK_PORT}/")
    page.locator(f"#{START_JOB_BUTTON_HOME_ID}").click()
    check_all_errors(page)

    email_input = page.locator(f"#{EMAIL_INPUT_USER_INFO_ID}")
    email_input.fill("test@ufz.de")
    expect(page.locator(f"#{NEXT_BUTTON_USER_INFO_ID}")).to_be_enabled(timeout=5000)
    page.locator(f"#{NEXT_BUTTON_USER_INFO_ID}").click()
    check_all_errors(page)

    page.locator(
        f"#{DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']"
    ).set_input_files(str(membership_file_path))

    job_id = page.url.split("/job/")[1].split("/")[0]

    start_time = time.time()
    while time.time() - start_time < 300:
        job_row = DataBaseManager.get_job_columns(job_id)
        street_processing = job_row["membership_upload"].get("street_processing")
        if street_processing == "COMPLETED":
            return job_id
        if street_processing == "FAILED":
            pytest.fail("Street processing failed during upload.")
        time.sleep(2)
    pytest.fail("Street processing did not complete within 300s.")


def test_street_click_marks_road_after_hard_load(
    page,
    dash_app,
    celery_worker,
    membership_file_path,
    worker_log_path,
    osm_cache_patch,
) -> None:
    """Clicking a street marks it — after a hard load of street-selection."""
    job_id = _upload_membership_and_wait(page, membership_file_path)

    # Hard load (browser refresh path) — not SPA navigation.
    page.goto(f"http://localhost:{FLASK_PORT}/job/{job_id}/street-selection")
    check_all_errors(page)

    pixel = _wait_for_street_pixel(page)
    assert pixel is not None, (
        "No street pixels rendered on the map after a hard load of the "
        "street-selection page — the street layer did not initialise."
    )

    page.mouse.click(pixel[0], pixel[1])
    expect(
        page.locator(f"#{SELECTED_BADGE_STREET_SELECTION_ID}")
    ).to_have_text("Selected: 1", timeout=5000)

    # Clicking the same spot again unmarks it.
    page.mouse.click(pixel[0], pixel[1])
    expect(
        page.locator(f"#{SELECTED_BADGE_STREET_SELECTION_ID}")
    ).to_have_text("Selected: 0", timeout=5000)

    # The map legend toggle collapses and re-expands the legend.
    legend_body = page.locator(f"#{MAP_LEGEND_COLLAPSE_SHARED_ID}")
    expect(legend_body).to_be_visible()
    page.locator(f"#{MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID}").click()
    expect(legend_body).not_to_be_visible(timeout=3000)
    page.locator(f"#{MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID}").click()
    expect(legend_body).to_be_visible(timeout=3000)
    check_all_errors(page)
