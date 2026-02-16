"""Test complete routing workflow from job creation to route download.

This test validates the end-to-end user journey:
1. Create a new job from the home page
2. Navigate through user info page
3. Upload a CSV file with member data
4. Navigate through street selection
5. Configure routing parameters
6. Start and wait for route computation
7. Verify the download URL is visible on the route download page
"""

from playwright.sync_api import expect

from test.help_functions_tests import check_all_errors
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    NEXT_BUTTON_ROUTE_COMPUTATION_ID,
    NEXT_BUTTON_ROUTING_PARAMS_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
    PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    START_BUTTON_ROUTE_COMPUTATION_ID,
    START_JOB_BUTTON_HOME_ID,
    USER_INFO_NEXT_BUTTON_USER_INFO_ID,
)


def test_complete_routing_workflow(
    page, dash_app, celery_worker, membership_file_path, predictor_file_path
) -> None:
    """Test the complete routing workflow from job creation to route download."""
    # === Home Page ===
    page.goto(f"http://localhost:{FLASK_PORT}/")
    page.locator(f"#{START_JOB_BUTTON_HOME_ID}").click()
    check_all_errors(page)

    # === User Info Page ===
    page.locator(f"#{USER_INFO_NEXT_BUTTON_USER_INFO_ID}").click()
    check_all_errors(page)

    # === Data Upload Page ===
    # Upload membership file
    page.locator(
        f"#{DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']"
    ).set_input_files(str(membership_file_path))
    # Upload predictor file (enabled after membership upload completes)
    expect(
        page.locator(f"#{PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']")
    ).to_be_enabled(timeout=30000)
    page.locator(
        f"#{PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']"
    ).set_input_files(str(predictor_file_path))
    expect(page.locator(f"#{NEXT_BUTTON_DATA_UPLOAD_ID}")).to_be_enabled(timeout=30000)
    page.locator(f"#{NEXT_BUTTON_DATA_UPLOAD_ID}").click()
    check_all_errors(page)

    # === Street Selection Page ===
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
        timeout=120000
    )
    page.locator(f"#{NEXT_BUTTON_ROUTE_COMPUTATION_ID}").click()
    # Note: check_all_errors skipped here as we're navigating to route_download

    # === Route Download Page ===
    # Verify that the download URL is visible
    expect(page.locator(f"#{DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID}")).to_be_visible()
    check_all_errors(page)
