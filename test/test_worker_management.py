"""Test worker management page task submission and revocation flow.

This test validates:
1. Navigating to the worker management page
2. Submitting a test task
3. Killing the active task
4. Verifying the task appears in the revoked tasks table
"""

from playwright.sync_api import expect

from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    LOADING_OVERLAY_SHARED_ID,
    REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID,
    TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID,
    WORKER_KILL_BTN_WORKER_MANAGEMENT_ID,
)
from test.help_functions_tests import check_all_errors


def test_submit_and_kill_task(page, dash_app):
    """Test submitting a test task, killing it, and verifying it appears in revoked tasks."""
    # Navigate to worker management page
    page.goto(f"http://localhost:{FLASK_PORT}/worker-management")

    # Wait for initial loading to complete (page load triggers refresh)
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
        timeout=5000
    )

    # Submit test task
    page.locator(f"#{TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID}").click()

    # Verify loading modal appears
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).to_be_visible(timeout=5000)

    # Wait for loading modal to disappear (refresh complete)
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
        timeout=10000
    )

    # Wait for table to have at least one row with data
    # Dash DataTables use .dash-cell class for cells
    first_cell = page.locator(
        f"#{ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID} .dash-cell"
    ).first
    expect(first_cell).to_be_visible(timeout=5000)

    # Extract task ID from first cell (task_id column)
    task_id = first_cell.text_content().strip()

    # Instead of selecting the row, directly set the task ID in the input field
    task_id_input = page.locator(f"#{SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID}")
    task_id_input.fill(task_id)

    # Click kill button (should be enabled now that input has value)
    page.locator(f"#{WORKER_KILL_BTN_WORKER_MANAGEMENT_ID}").click()

    # Wait for loading modal to appear and disappear
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).to_be_visible(timeout=5000)
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
        timeout=10000
    )

    # Verify task ID appears in revoked tasks table
    revoked_table_text = page.locator(
        f"#{REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID}"
    ).text_content()
    assert (
        task_id in revoked_table_text
    ), f"Task ID {task_id} not found in revoked tasks table"

    # Check for any errors
    check_all_errors(page)
