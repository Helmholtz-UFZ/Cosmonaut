"""Test worker management page task submission and revocation flow.

This test validates:
1. Navigating to the worker management page
2. Submitting a test task
3. Killing the active task
4. Verifying the task appears in the revoked tasks table
"""

import logging

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
    # The Celery worker may take time to pick up the task, and DataTable cells
    # render asynchronously after the callback returns with new data.
    active_task_cell_selector = f"#{ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID} .dash-cell"
    first_cell = page.locator(active_task_cell_selector).first

    max_attempts = 15  # Total ~30s budget for worker pickup + render
    for attempt in range(max_attempts):
        # Refresh to poll latest task state from Celery
        page.locator(f"#{WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID}").click()
        expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
            timeout=10000
        )

        # Key fix: Use Playwright's async waiting instead of synchronous is_visible()
        # This properly waits for React to finish rendering after data prop update
        try:
            expect(first_cell).to_be_visible(timeout=2000)
            break
        except AssertionError:
            if attempt >= max_attempts - 1:
                # Re-raise with clear message on final attempt
                raise AssertionError(
                    f"Task did not appear in active tasks table after {max_attempts} "
                    "refresh attempts. Possible causes: Celery worker not processing "
                    "tasks, or test task not submitted."
                )
            # Wait before next refresh attempt
            page.wait_for_timeout(1500)

    # Extract task ID from first cell (task_id column)
    task_id = first_cell.text_content().strip()

    # Instead of selecting the row, directly set the task ID in the input field
    task_id_input = page.locator(f"#{SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID}")
    task_id_input.fill(task_id)

    # Wait for button to be clickable and click kill button
    kill_button = page.locator(f"#{WORKER_KILL_BTN_WORKER_MANAGEMENT_ID}")
    expect(kill_button).to_be_enabled(timeout=5000)
    kill_button.click()

    # Wait for loading modal to appear and disappear
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).to_be_visible(timeout=5000)
    expect(page.locator(f"#{LOADING_OVERLAY_SHARED_ID}")).not_to_be_visible(
        timeout=10000
    )

    # Verify task ID appears in revoked tasks table
    # Use expect().to_contain_text() which retries until text appears or timeout
    expect(
        page.locator(f"#{REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID}")
    ).to_contain_text(task_id, timeout=10000)

    # Check for any errors
    check_all_errors(page)
