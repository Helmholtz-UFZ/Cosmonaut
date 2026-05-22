"""Collect user email for job notifications.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This page allows you to provide an email address to receive notifications about
your routing job. Email notifications will be sent when:

- Your job has been successfully submitted for processing
- Your routing calculation has completed
- Any errors occur during processing

The email field includes live validation to ensure proper formatting before you can
proceed. Providing an email is optional but recommended for tracking long-running
jobs that process in the background.

Once you enter a valid email address (or skip this step by proceeding without one),
click "Next" to continue to the data upload page where you'll provide your
membership locations for route planning.

# Notes (This section is for developer notes and will not appear in the user documentation.)

Email validation uses pydantic's check_email function for format verification.
The email is stored in the job model and accessible throughout the workflow.
"""

import logging

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html, register_page
from dash.exceptions import PreventUpdate

from cosmonaut_app.constants.general import JOB_STATUS_PENDING
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    URL_SHARED_ID,
    EMAIL_HELPER_TEXT_USER_INFO_ID,
    EMAIL_INPUT_USER_INFO_ID,
    EMAIL_VISIBILITY_NOTICE_COLLAPSE_USER_INFO_ID,
    NEXT_BUTTON_USER_INFO_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.layout import (
    build_url_step,
    create_card_input,
    create_reset_banner,
    create_reset_modal,
    page_container_fullscreen_layout,
    progress_footer,
)
from cosmonaut_app.pydantic_models import check_email

log = logging.getLogger(__name__)

register_page(
    __name__,
    path_template="/job/<job_id>/user-info",
    name="User Information",
    title="User Info",
    description="Enter your email address for this job.",
)


def layout(job_id):
    log.info(f"Creating layout page {__name__} for {job_id}")
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING

    card_body = []

    # Add reset banner if not PENDING
    if not is_active:
        card_body.append(create_reset_banner(job_id, status))

    # Determine initial helper text and collapse state from stored email
    stored_email = job.model.email
    if not stored_email:
        _initial_helper = (
            "Optional — without an email you won't receive job-completion notifications."
        )
        _initial_helper_cls = "text-warning small"
        _initial_valid = False
        _initial_invalid = False
        _initial_collapse_open = False
    else:
        try:
            check_email(stored_email)
            _initial_helper = "Looks good — you'll be notified when this job completes."
            _initial_helper_cls = "text-success small"
            _initial_valid = True
            _initial_invalid = False
            _initial_collapse_open = True
        except ValueError:
            _initial_helper = "Please enter a valid email address."
            _initial_helper_cls = "text-danger small"
            _initial_valid = False
            _initial_invalid = True
            _initial_collapse_open = False

    # Add form components
    card_body.extend(
        [
            html.P(
                "Enter your email to receive notifications for this job.",
                className="text-muted",
            ),
            dbc.Label(
                "Email address",
                html_for=EMAIL_INPUT_USER_INFO_ID,
                className="mt-2",
            ),
            dbc.Input(
                id=EMAIL_INPUT_USER_INFO_ID,
                type="email",
                value=stored_email,
                valid=_initial_valid,
                invalid=_initial_invalid,
                autoFocus=True,
                disabled=not is_active,
            ),
            dbc.Collapse(
                dbc.FormText(
                    "Warning: Your email is visible from inside the UFZ network.",
                    color="warning",
                    className="d-block",
                ),
                id=EMAIL_VISIBILITY_NOTICE_COLLAPSE_USER_INFO_ID,
                is_open=_initial_collapse_open,
            ),
            html.Div(
                _initial_helper,
                id=EMAIL_HELPER_TEXT_USER_INFO_ID,
                className=_initial_helper_cls,
            ),
            dbc.FormText(
                [
                    html.I(className="bi bi-shield-check me-1"),
                    "We never share your email.",
                ],
                color="secondary",
            ),
        ]
    )

    # Add reset modal
    card_body.append(create_reset_modal())

    # Add store
    card_body.append(dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id))

    footer = progress_footer(
        next_id=NEXT_BUTTON_USER_INFO_ID,
    )
    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
        completed_steps=job.get_completed_steps(),
    )

    return page_container_fullscreen_layout(input_container)


@callback(
    Output(EMAIL_INPUT_USER_INFO_ID, "valid"),
    Output(EMAIL_INPUT_USER_INFO_ID, "invalid"),
    Output(NEXT_BUTTON_USER_INFO_ID, "disabled"),
    Output(EMAIL_HELPER_TEXT_USER_INFO_ID, "children"),
    Output(EMAIL_HELPER_TEXT_USER_INFO_ID, "className"),
    Output(EMAIL_VISIBILITY_NOTICE_COLLAPSE_USER_INFO_ID, "is_open"),
    Input(EMAIL_INPUT_USER_INFO_ID, "value"),
)
def validate_email(value):
    """Live email validation — three states: empty (optional), invalid, valid."""
    log.debug(f"Validating email: {value}")
    if not value:
        return (
            False,
            False,
            False,
            "Optional — without an email you won't receive job-completion notifications.",
            "text-warning small",
            False,
        )
    try:
        check_email(value)
        return (
            True,
            False,
            False,
            [
                html.I(className="bi bi-check-lg me-1"),
                "You'll be notified when this job completes.",
            ],
            "text-success small",
            True,
        )
    except ValueError:
        return (
            False,
            True,
            True,
            "Please enter a valid email address.",
            "text-danger small",
            False,
        )


@callback(
    Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
    Input(NEXT_BUTTON_USER_INFO_ID, "n_clicks"),
    State(EMAIL_INPUT_USER_INFO_ID, "value"),
    State(URL_SHARED_ID, "pathname"),
    prevent_initial_call=True,
)
def go_to_upload_page(n_clicks: int | None, email: str | None, pathname: str | None):
    if not n_clicks or not pathname:
        raise PreventUpdate

    try:
        check_email(email or "")
    except ValueError:
        raise PreventUpdate

    job_id = pathname.split("/")[2]
    job = CosmonautJob(job_id=job_id, sync_files=False)
    job.model.email = email
    job.model.stage = max(job.model.stage, 1)
    job.save(sync_files=False)

    log.info(f"Storing email {email} for job {job_id}")

    return build_url_step("data_upload", job_id)
