"""Error handling utilities for Dash apps.

The modal, the response table and ``handle_error`` come from
``cosmo_suite.error_handling``. Only what the framework cannot know stays here:
two domain exceptions and the maintainer notification.

Two deliberate divergences, both of the kind that fails silently
(see ../docs/conventions/framework_integration.md):

- ``ObjectStorageError`` is **imported, not defined**. The framework's storage
  functions raise its class; a local class of the same name is a different class,
  so every ``except ObjectStorageError`` would quietly stop catching, with no
  import error and no failing test.
- ``FileValidationError`` is **defined here, not imported**, which is the same
  trap in the other direction. The framework's class takes no arguments and
  carries no message; this app raises it with the parser's validation text and
  shows ``str(e)`` to the user (``pages/data_upload.py``). Importing the
  framework's would blank that message and break the four raise sites with a
  TypeError. Never let both classes reach one process.
"""

import logging
from functools import partial

import psycopg2
from cosmo_suite.error_handling import JobNotFound as JobNotFound
from cosmo_suite.error_handling import error_modal as error_modal
from cosmo_suite.error_handling import error_responds_dict
from cosmo_suite.error_handling import handle_error as handle_error
from cosmo_suite.object_storage_manager import ObjectStorageError as ObjectStorageError

from cosmonaut_app.config import MAINTAINER_EMAIL
from cosmonaut_app.email_service import send_mail

log = logging.getLogger(__name__)


class WrongCeleryTaskId(Exception):
    """Custom exception for when an invalid Celery task ID is provided."""

    def __init__(self, task_id):
        """Add task_id as attribute and format error message."""
        self.task_id = task_id
        super().__init__(f"Invalid Celery task ID format: '{task_id}'")


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


# Extend the framework's table rather than replace it: the framework keys its own
# entry on *its* FileValidationError, which this app never raises, so the local
# class needs an entry of its own or a validation error would fall through to the
# generic "Internal Error".
error_responds_dict.update(
    {
        psycopg2.DatabaseError: (
            "Database Connection Error",
            "Unfortunately, it is not possible to connect to the job database. Please try again later.",  # noqa
        ),
        WrongCeleryTaskId: (
            "Invalid Task ID",
            "The task ID '{task_id}' is not a valid Celery task ID format. Task IDs must be UUIDs.",  # noqa
        ),
        FileValidationError: (
            "File Validation Error",
            "The uploaded file could not be validated. Please check the file format and try again.",  # noqa
        ),
    }
)


def notify_maintainer(error):
    """Mail the maintainer about an error the framework classified as unhandled.

    Wired in app.py as ``on_error=partial(handle_error, on_unhandled=...)``. The
    framework never imports a mail service — it only calls what it is handed —
    so **forgetting the hook makes the maintainer mails vanish silently**.
    test/test_error_handling.py guards that.

    The framework already logs the traceback and the callback context before
    calling this, so this only sends.
    """
    send_mail(MAINTAINER_EMAIL, f"COSMONAUT Error: {error}", repr(error))


# Ready-made for `Dash(on_error=...)`, so the hook cannot be forgotten at the
# call site by writing `on_error=handle_error`.
handle_error_with_notification = partial(handle_error, on_unhandled=notify_maintainer)
