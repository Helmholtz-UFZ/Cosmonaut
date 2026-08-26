"""Guards for the two error-handling seams that fail silently.

Both failures are invisible without a test: the app keeps running, no exception
is raised, no log line says anything is wrong. See
docs/conventions/framework_integration.md.
"""

import logging
from contextlib import contextmanager
from unittest import mock

import pytest
from cosmo_suite.error_handling import error_responds_dict
from cosmo_suite.object_storage_manager import ObjectStorageError as FrameworkError

from cosmonaut_app.error_handling import (
    ERROR_RESPONSES,
    FileValidationError,
    ObjectStorageError,
    WrongCeleryTaskId,
    handle_error_with_notification,
    notify_maintainer,
)

log = logging.getLogger(__name__)


@contextmanager
def _dash_stubbed():
    """Stub the Dash side of handle_error.

    dash.ctx.triggered is json.dumps()-ed by the framework handler, so it has to
    be a real serializable value rather than a MagicMock.
    """
    with (
        mock.patch("cosmo_suite.error_handling.dash") as dash_mod,
        mock.patch("cosmo_suite.error_handling.set_props"),
    ):
        dash_mod.ctx.triggered = [{"prop_id": "x.n_clicks", "value": 1}]
        yield


def test_object_storage_error_is_the_framework_class():
    """`except ObjectStorageError` must catch what framework code raises.

    A local class of the same name would be a *different* class: the except
    clause still reads correctly and never fires again, the error escapes to the
    generic handler, and the user sees "Internal Error" instead of the storage
    message. No import error, no failing test — hence this one.
    """
    assert ObjectStorageError is FrameworkError

    try:
        raise FrameworkError("from framework code")
    except ObjectStorageError:
        caught = True
    assert caught, "except ObjectStorageError did not catch the framework class"

    assert FrameworkError in error_responds_dict


def test_file_validation_error_stays_local_and_carries_its_message():
    """The framework's namesake takes no message; this app shows str(e) to users.

    Importing the framework class would blank the validation text in
    pages/data_upload.py and break the raise sites with a TypeError.
    """
    from cosmo_suite.error_handling import FileValidationError as FrameworkFileError

    assert FileValidationError is not FrameworkFileError

    err = FileValidationError("column 'x' is missing")
    assert str(err) == "column 'x' is missing"

    # The app's class needs its own response entry — the framework keys its entry
    # on its own class, which this app never raises. Laid over error_responds_dict
    # via handle_error's error_responses parameter, not mutated into it.
    assert FileValidationError in ERROR_RESPONSES


def test_domain_exceptions_have_response_entries():
    """The app's own exceptions carry a response entry the modal can use."""
    for exc in (WrongCeleryTaskId, FileValidationError):
        assert exc in ERROR_RESPONSES, f"{exc.__name__} has no response entry"
    assert ObjectStorageError in error_responds_dict


def test_on_unhandled_is_called_for_unexpected_errors():
    """Forgetting the hook makes the maintainer mails vanish without a trace.

    The framework never imports a mail service; it calls what it is handed. If
    app.py wires `on_error=handle_error` instead of the partial, nothing fails —
    the mails simply stop.
    """
    with (
        _dash_stubbed(),
        mock.patch("cosmonaut_app.error_handling.send_mail") as send_mail,
    ):
        handle_error_with_notification(RuntimeError("boom"))

    assert send_mail.call_count == 1, "on_unhandled hook was not called"
    recipients, subject, _body = send_mail.call_args[0]
    assert "boom" in subject


def test_expected_errors_do_not_notify():
    """Only unexpected errors are worth a mail — a missing job is not a defect."""
    from cosmonaut_app.error_handling import JobNotFound

    with (
        _dash_stubbed(),
        mock.patch("cosmonaut_app.error_handling.send_mail") as send_mail,
    ):
        handle_error_with_notification(JobNotFound("missing_job"))

    assert send_mail.call_count == 0, "a routine JobNotFound triggered a mail"


def test_notify_maintainer_failure_does_not_escape():
    """A dead SMTP server must not take the error modal down with it."""
    with (
        _dash_stubbed(),
        mock.patch(
            "cosmonaut_app.error_handling.send_mail", side_effect=OSError("no smtp")
        ),
    ):
        handle_error_with_notification(RuntimeError("boom"))

    with pytest.raises(OSError):
        with mock.patch(
            "cosmonaut_app.error_handling.send_mail", side_effect=OSError("no smtp")
        ):
            notify_maintainer(RuntimeError("boom"))
