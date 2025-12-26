"""Test complete routing workflow from job creation to route start.

This test validates the end-to-end user journey:
1. Create a new job from the home page
2. Navigate through user info page
3. Upload a CSV file with member data
4. Navigate through street selection
5. Configure routing parameters
6. Verify the Start Route button is visible on the route download page
"""

from playwright.sync_api import expect

from test.help_functions_tests import check_all_errors
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    NEXT_BUTTON_ROUTING_PARAMS_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
    START_JOB_BUTTON_HOME_ID,
    START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
    USER_INFO_NEXT_BUTTON_USER_INFO_ID,
)


def test_complete_routing_workflow(page, dash_app, celery_worker) -> None:
    """Test the complete routing workflow from job creation to route start."""
    # === Home Page ===
    page.goto(f"http://localhost:{FLASK_PORT}/")
    page.locator(f"#{START_JOB_BUTTON_HOME_ID}").click()
    check_all_errors(page)

    # === User Info Page ===
    page.locator(f"#{USER_INFO_NEXT_BUTTON_USER_INFO_ID}").click()
    check_all_errors(page)

    # === Data Upload Page ===
    # Upload CSV file using the file input within the Upload component
    page.locator(
        f"#{DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID} input[type='file']"
    ).set_input_files("test/test_files/memberships.csv")
    page.locator(f"#{NEXT_BUTTON_DATA_UPLOAD_ID}").click()
    check_all_errors(page)

    # === Street Selection Page ===
    page.locator(f"#{NEXT_BUTTON_STREET_SELECTION_ID}").click()
    check_all_errors(page)

    # === Routing Parameters Page ===
    page.locator(f"#{NEXT_BUTTON_ROUTING_PARAMS_ID}").click()
    check_all_errors(page)

    # === Route Download Page ===
    # Verify that the Start Route button is visible
    expect(page.locator(f"#{START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID}")).to_be_visible()
    check_all_errors(page)
