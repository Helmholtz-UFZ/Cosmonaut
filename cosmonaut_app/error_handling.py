"""Error handling utilities for Dash apps."""

import json
import logging
import traceback

import dash
import dash_bootstrap_components as dbc
import psycopg2
from dash import set_props
from sqlalchemy.exc import DatabaseError, OperationalError
from werkzeug.exceptions import NotFound

from cosmonaut_app.config import MAINTAINER_EMAIL
from cosmonaut_app.constants.html_ids import (
    ERROR_MODAL_MESSAGE_SHARED_ID,
    ERROR_MODAL_SHARED_ID,
    ERROR_MODAL_TITLE_SHARED_ID,
)
from cosmonaut_app.email_service import send_mail

log = logging.getLogger(__name__)


class JobNotFound(Exception):
    """Custom exception for when a job is not found."""

    def __init__(self, job_id):
        """Add job id as attribute and format error message."""
        self.job_id = job_id
        super().__init__(f"Job with ID '{job_id}' not found")


class WrongCeleryTaskId(Exception):
    """Custom exception for when an invalid Celery task ID is provided."""

    def __init__(self, task_id):
        """Add task_id as attribute and format error message."""
        self.task_id = task_id
        super().__init__(f"Invalid Celery task ID format: '{task_id}'")


class ObjectStorageError(Exception):
    """Exception raised for errors in the ObjectStorageManager class."""

    def __init__(self, message="An error occurred while managing object storage."):
        """Initialize the ObjectStorageError with a message."""
        self.message = message
        super().__init__(message)


class FileValidationError(Exception):
    """Signals that a user-uploaded input file failed validation.

    Raised exclusively inside CosmonautJob.upload_membership() and
    CosmonautJob.upload_predictor() when the uploaded CSV fails format
    validation or cross-file consistency checks (via the sensor-routing
    parsers). The error message is the raw validation message from the
    parser, suitable for display directly to the user.

    Contract:
    - Raised only in upload methods on CosmonautJob.
    - Caught only in the upload callback in data_upload.py.
    - Must never escape to handle_error(). Reaching handle_error()
      means the callback is missing an except clause and is a bug.
    - Do not raise outside of input file validation contexts.
    """

    def __init__(self, message):
        """Store the validation message for inline display to the user."""
        self.message = message
        super().__init__(message)


database_error_title = "Database Connection Error"
database_error_message = "Unfortunately, it is not possible to connect to the job database. Please try again later."  # noqa
error_responds_dict = {
    psycopg2.DatabaseError: (
        database_error_title,
        database_error_message,
    ),
    DatabaseError: (
        database_error_title,
        database_error_message,
    ),
    OperationalError: (
        database_error_title,
        database_error_message,
    ),
    NotFound: ("File Not Found", "The file could not be found."),
    Exception: ("Internal Error", "Ups this should not happen. An error occurred."),
    JobNotFound: (
        "Job Not Found",
        "Could not find the job '{job_id}'. Visit input to make a new submission.",
    ),
    WrongCeleryTaskId: (
        "Invalid Task ID",
        "The task ID '{task_id}' is not a valid Celery task ID format. Task IDs must be UUIDs.",
    ),
    FileValidationError: (
        "File Validation Error",
        "The uploaded file could not be validated. Please check the file format and try again.",
    ),
    ObjectStorageError: (
        "Object Storage Error",
        "An error occurred while accessing object storage. Please try again later.",
    ),
}
error_modal = dbc.Modal(
    [
        dbc.ModalHeader(
            dbc.ModalTitle("Error"),
            id=ERROR_MODAL_TITLE_SHARED_ID,
            close_button=False,
            className="bg-light",
        ),
        dbc.ModalBody(
            id=ERROR_MODAL_MESSAGE_SHARED_ID, className="text-danger bg-light"
        ),
        dbc.ModalFooter(className="bg-light"),
    ],
    id=ERROR_MODAL_SHARED_ID,
    is_open=False,
)


def _truncate_string(value, max_length=200, head_length=100, tail_length=50):
    """Truncate a string if it exceeds max_length."""
    if not isinstance(value, str):
        return value
    if len(value) <= max_length:
        return value
    return f"{value[:head_length]}...{value[-tail_length:]}"


def _truncate_data(data):
    """Recursively truncate long strings in data structures."""
    if isinstance(data, dict):
        return {key: _truncate_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_truncate_data(item) for item in data]
    elif isinstance(data, str):
        return _truncate_string(data)
    else:
        return data


def handle_error(error):
    """Handle the error and return a formatted message."""
    log.debug(f"Error: {error}")

    # Define here the error that should be reported
    if not isinstance(
        error,
        (JobNotFound, WrongCeleryTaskId, FileValidationError),
    ):
        callback_context = dash.ctx
        truncated_triggered = _truncate_data(callback_context.triggered)
        email_subject = f"COSMONAUT Error: {error}"
        email_body = (
            f"Traceback info: {traceback.format_exc()}\n\n"
            f"Input info: {json.dumps(truncated_triggered)}"
        )
        try:
            log.debug(f"Send mail to {MAINTAINER_EMAIL}")
            send_mail(MAINTAINER_EMAIL, email_subject, email_body)
        except Exception:  # noqa - must not let email failure crash the error handler
            log.error("Failed to send maintainer error email", exc_info=True)
        log.error(f"Unhandled error: {error}")
        log.error(email_body)

    error_type = type(error) if type(error) in error_responds_dict else Exception
    error_title = error_responds_dict[error_type][0]
    error_message = error_responds_dict[error_type][1]

    try:
        error_message = error_message.format(job_id=error.job_id)
    except AttributeError:
        # If the error does not have a job_id attribute, we just use the message as is.
        pass

    try:
        error_message = error_message.format(task_id=error.task_id)
    except AttributeError:
        # If the error does not have a task_id attribute, we just use the message as is.
        pass

    log.error(f"{error_title}: {error_message}")
    log.error(f"Error details: {traceback.format_exc()}")
    set_props(ERROR_MODAL_SHARED_ID, {"is_open": True})
    set_props(ERROR_MODAL_TITLE_SHARED_ID, {"children": error_title})
    set_props(ERROR_MODAL_MESSAGE_SHARED_ID, {"children": error_message})
