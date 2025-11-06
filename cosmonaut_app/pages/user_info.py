import re

import logging
from dash import html, register_page, callback, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.constants.html_ids import (
    URL_SHARED_ID,
    USER_INFO_EMAIL_INPUT_USER_INFO_ID,
    USER_INFO_NEXT_BUTTON_USER_INFO_ID,
)
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    progress_footer,
    default_map,
    build_url_step,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob

register_page(
    __name__,
    path_template="/job/<job_id>/user-info",
    name="User Information",
    title="User Info",
    description="Enter your email address for this job.",
)

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


def layout(job_id):
    job = CosmonautJob(job_id=job_id)
    email_value = job.email if job.email else "you@example.org"

    card_body = [
        html.P(
            "Enter your email to receive notifications for this job.",
            className="text-muted",
        ),
        dbc.Label(
            "Email address",
            html_for=USER_INFO_EMAIL_INPUT_USER_INFO_ID,
            className="mt-2",
        ),
        dbc.Input(
            id=USER_INFO_EMAIL_INPUT_USER_INFO_ID,
            type="email",
            value=email_value,
            autoFocus=True,
        ),
        dbc.FormText(
            [html.I(className="bi bi-shield-check me-1"), "We never share your email."],
            color="secondary",
        ),
        dbc.FormFeedback("Looks good!", type="valid"),
        dbc.FormFeedback("Please enter a valid email.", type="invalid"),
    ]

    footer = progress_footer(
        next_id=USER_INFO_NEXT_BUTTON_USER_INFO_ID,
    )
    map = default_map
    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )

    return page_container_split_layout(map, input_container)


@callback(
    Output(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "valid"),
    Output(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "invalid"),
    Output(USER_INFO_NEXT_BUTTON_USER_INFO_ID, "disabled"),
    Input(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
)
def validate_email(value):
    """Live email validation -> toggles input valid/invalid and enables Next button."""
    if not value:
        return False, False, True
    is_valid = re.match(EMAIL_REGEX, value) is not None
    return (True, False, False) if is_valid else (False, True, True)


@callback(
    Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
    Input(USER_INFO_NEXT_BUTTON_USER_INFO_ID, "n_clicks"),
    State(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
    State(URL_SHARED_ID, "pathname"),
    prevent_initial_call=True,
)
def go_to_upload_page(n_clicks: int | None, email: str | None, pathname: str | None):
    if not n_clicks or not pathname:
        raise PreventUpdate

    if not email or not re.match(EMAIL_REGEX, email):
        raise PreventUpdate

    job_id = pathname.split("/")[2]
    job = CosmonautJob(job_id=job_id)
    job.email = email
    job.save()

    logging.info(f"Storing email {email} for job {job_id}")

    return build_url_step("data_upload", job_id)
