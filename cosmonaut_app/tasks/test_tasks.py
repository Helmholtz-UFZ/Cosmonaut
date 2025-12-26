"""Test tasks for COSMONAUT App.

This module contains simple test tasks for verifying Celery worker functionality.
"""

import logging
import time

from celery import Task

log = logging.getLogger(__name__)


class TestTask(Task):
    """Base class for test tasks."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        log.error(f"Test task {task_id} failed: {exc}")


def test_sleep_task(self):
    """Simple test task that sleeps for 4 seconds.

    Returns:
        dict: Task result with status and duration
    """
    start_time = time.time()
    log.info("Test sleep task started")

    time.sleep(40)

    duration = time.time() - start_time
    log.info(f"Test sleep task completed after {duration:.2f} seconds")

    return {
        "status": "completed",
        "duration": duration,
        "message": "Test task completed successfully",
    }
