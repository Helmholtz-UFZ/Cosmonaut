"""Test worker management page task submission and revocation flow.

This test validates:
1. Navigating to the worker management page
2. Submitting a test task
3. Killing the active task
4. Verifying the task appears in the revoked tasks table
"""

import logging

from time import sleep

from playwright.sync_api import expect

from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.constants.html_ids import (
    ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    LOADING_OVERLAY_SHARED_ID,
    REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID,
    TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID,
    WORKER_KILL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID,
)
from test.help_functions_tests import check_all_errors


def test_submit_and_kill_task(page, dash_app, celery_worker):
    """Test submitting a test task, killing it, and verifying it appears in revoked tasks."""
    # Navigate to worker management page
    page.goto(f"http://localhost:{FLASK_PORT}/worker-management")

    logging.info("Visited worker management page, waiting for loading to complete")
    # Wait for initial loading to complete (page load triggers refresh)
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
        timeout=5000
    )

    logging.info("Loading complete, submitting test task")

    # Submit test task
    page.locator(f"#{TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID}").click()

    logging.info("Submitted test task, waiting for it to appear in active tasks table")

    # Verify loading modal appears
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).to_be_visible(timeout=5000)

    # Wait for loading modal to disappear (refresh complete)
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
        timeout=10000
    )

    # Wait for task to appear in active tasks table
    # The task may not be picked up by the worker immediately after submission,
    # so we need to poll/retry. Use a longer timeout and let Playwright retry.
    # Dash DataTables use .dash-cell class for cells
    first_cell = page.locator(
        f"#{ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID} .dash-cell"
    ).first

    # Poll until task appears - the page auto-refreshes but we may need to wait
    # for the worker to actually start executing the task
    max_attempts = 10
    for attempt in range(max_attempts):
        # Click refresh to get latest data
        page.locator(f"#{WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID}").click()
        expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
            timeout=10000
        )

        # Check if task is now visible
        if first_cell.is_visible():
            break

        if attempt < max_attempts - 1:
            sleep(1)  # Brief wait before next refresh attempt
    else:
        # Final assertion to get proper error message if task never appeared
        expect(first_cell).to_be_visible(timeout=1000)

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
