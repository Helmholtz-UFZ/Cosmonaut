import contextlib
import datetime
import os
import shutil
import time
from unittest import mock

import pytest

from cosmonaut_app.constants.general import JOB_STATUS_COMPLETED
from cosmonaut_app.cosmonaut_job import CosmonautJob


def check_all_errors(page):
    """Check for errors on the page.

    This function checks for:
    - Console errors (SEVERE/ERROR level, excluding favicon errors)
    - JavaScript errors
    - Broken images
    """
    time.sleep(1)  # Allow page to load
    errors = []

    # Console errors - get from browser console logs
    console_logs = page.context.pages[0].evaluate(
        """() => {
            return window.__CONSOLE_LOGS__ || [];
        }"""
    )

    # Filter severe/error console messages
    console_errors = [
        log
        for log in console_logs
        if isinstance(log, dict)
        and log.get("level") in ["SEVERE", "ERROR"]
        and "favicon" not in str(log.get("message", "")).lower()
    ]
    if console_errors:
        errors.extend([f"Console: {log['message']}" for log in console_errors])

    # JavaScript errors - check for error elements or window.jsErrors
    js_errors = page.evaluate(
        """() => {
            const errors = window.jsErrors || [];
            const errorElements = Array.from(document.querySelectorAll('[data-error]'))
                .map(el => el.dataset.error);
            return errors.concat(errorElements);
        }"""
    )
    if js_errors:
        errors.extend([f"JS Error: {err}" for err in js_errors if err])

    # Wait for images to load
    page.wait_for_load_state("networkidle", timeout=5000)

    # Check for broken images (exclude Leaflet tile images which may have
    # empty/invalid src before tile URLs are populated by callbacks)
    broken_images = page.evaluate(
        """() => {
            return Array.from(document.querySelectorAll('img'))
                .filter(img => !img.closest('.leaflet-tile-pane'))
                .filter(img => img.complete && img.naturalWidth === 0 && img.src !== '')
                .map(img => img.src);
        }"""
    )
    if broken_images:
        errors.extend([f"Broken image: {img}" for img in broken_images])

    if errors:
        pytest.fail("Errors detected:\n" + "\n".join(errors))


def job_row(job_id, *, start_date=None, submitted=True):
    """Return a complete ``jobs`` row for DataBaseManager.add_entry.

    Args:
        job_id: The row's job id.
        start_date: Defaults to today. Never NULL: every real job has one, and
            the cleanup reads it for every row in the table.
        submitted: Whether the job counts as submitted for retention.
    """
    return {
        "job_id": job_id,
        "start_date": datetime.date.today() if start_date is None else start_date,
        "submitted": submitted,
        "email": "example@gmail.com",
        "notified_end": False,
        "stage": 3,
        "status": JOB_STATUS_COMPLETED,
        "version": "1.0",
        "membership_upload": {"file_name": "test.csv"},
        "predictor_upload": {"file_name": "test_predictors.csv"},
        "epsg": 4326,
        "config": {},
    }


@contextlib.contextmanager
def another_pod_meanwhile(job):
    """Yield job as loaded on a pod with its own disk; this pod's work dir is
    parked meanwhile and comes back exactly as it was."""
    parked = job.working_dir + ".parked"
    os.rename(job.working_dir, parked)
    try:
        yield CosmonautJob(job_id=job.model.job_id)
    finally:
        shutil.rmtree(job.working_dir, ignore_errors=True)
        os.rename(parked, job.working_dir)


def celery_says(status):
    """Patch the Celery state lookup to report status."""
    return mock.patch(
        "cosmonaut_app.cosmonaut_job.background_job_manager.get_job_status",
        return_value={"status": status},
    )
