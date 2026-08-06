"""Test worker management page task submission and revocation flow.

This test validates:
1. Navigating to the worker management page
2. Submitting a test task
3. Selecting the task row and killing it via confirmation modal
4. Verifying the task disappears from active and appears in revoked with REVOKED status
"""

import logging

from cosmo_suite.constants import (
    ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    KILL_MODAL_CONFIRM_BUTTON_WORKER_MANAGEMENT_ID,
    KILL_MODAL_WORKER_MANAGEMENT_ID,
    LOADING_OVERLAY_MODAL_SHARED_ID,
    REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID,
    WORKER_KILL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID,
)
from playwright.sync_api import expect

from cosmonaut_app.config import PORT
from test.help_functions_tests import check_all_errors

log = logging.getLogger(__name__)


def click_refresh_and_wait(page):
    """Click refresh button and wait for the loading overlay to close."""
    page.locator(f"#{WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID}").click()
    expect(page.locator(f"#{LOADING_OVERLAY_MODAL_SHARED_ID}")).not_to_be_visible(
        timeout=20000
    )


def wait_for_overlay_close(page):
    """Wait for the loading overlay to close."""
    expect(page.locator(f"#{LOADING_OVERLAY_MODAL_SHARED_ID}")).not_to_be_visible(
        timeout=20000
    )


def test_submit_and_kill_task(page, dash_app, celery_worker):
    """Test submitting a test task, killing it via modal, and verifying it appears in revoked tasks."""
    page.goto(f"http://localhost:{PORT}/worker-management")
    wait_for_overlay_close(page)

    # Submit test task
    page.locator(f"#{TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID}").click()
    wait_for_overlay_close(page)

    # Poll until task appears in active tasks table
    active_row = page.locator(
        f"#{ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID} .ag-center-cols-container .ag-row"
    ).first

    max_attempts = 10
    for attempt in range(max_attempts):
        click_refresh_and_wait(page)
        try:
            expect(active_row).to_be_visible(timeout=2000)
            break
        except AssertionError:
            if attempt >= max_attempts - 1:
                raise AssertionError(
                    "Task did not appear in active tasks table after "
                    f"{max_attempts} refresh attempts."
                )

    # Extract task ID — use inner_text() which waits for AG Grid rendering
    task_id_cell = active_row.locator('[col-id="task_id"]')
    expect(task_id_cell).not_to_be_empty(timeout=5000)
    task_id = task_id_cell.inner_text().strip()

    # Select row and kill via modal
    page.locator(
        f"#{ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID} .ag-row .ag-selection-checkbox"
    ).first.click()

    kill_button = page.locator(f"#{WORKER_KILL_BTN_WORKER_MANAGEMENT_ID}")
    expect(kill_button).to_be_enabled(timeout=5000)
    kill_button.click()

    expect(page.locator(f"#{KILL_MODAL_WORKER_MANAGEMENT_ID}")).to_be_visible(
        timeout=5000
    )
    page.locator(f"#{KILL_MODAL_CONFIRM_BUTTON_WORKER_MANAGEMENT_ID}").click()
    wait_for_overlay_close(page)

    # Poll until task appears in revoked table with REVOKED status
    active_table = page.locator(f"#{ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID}")
    revoked_table = page.locator(f"#{REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID}")

    max_attempts = 5
    for attempt in range(max_attempts):
        click_refresh_and_wait(page)
        try:
            expect(revoked_table).to_contain_text(task_id, timeout=2000)
            expect(revoked_table).to_contain_text("REVOKED", timeout=2000)
            expect(active_table).not_to_contain_text(task_id, timeout=2000)
            break
        except AssertionError:
            if attempt >= max_attempts - 1:
                raise AssertionError(
                    f"Task {task_id} not properly revoked after {max_attempts} "
                    f"refresh attempts. "
                    f"Revoked table: {revoked_table.text_content()}"
                )

    check_all_errors(page)
