"""Constants package for COSMONAUT application.

This package contains all application constants.
Import constants explicitly from their respective modules:
    from cosmonaut_app.constants.html_ids import SOME_CONSTANT_ID
"""

# Constants for file names
SOLUTION_FILE = "solution_transformed.json"
LOG_FILE_NAME = "worker.log"

# Job status constants
JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_FAILED = "FAILED"
