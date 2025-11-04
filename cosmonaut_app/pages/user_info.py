# pages/user_info.py
import re
import logging
from dash import html, register_page, callback, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.ui.page import page_layout, progress_footer
from cosmonaut_app.constants.html_ids import (
    URL_DIV_NAV_SHARED_ID,
    USER_INFO_CONTENT_DIV_USER_INFO_ID,
    USER_INFO_EMAIL_INPUT_USER_INFO_ID,
    USER_INFO_NEXT_BUTTON_USER_INFO_ID,
)

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


def layout(job_id=None, **kwargs):
    body = [
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
            placeholder="you@example.org",
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
        prev=None,
        next_=dbc.Button(
            [html.I(className="bi bi-arrow-right-circle me-1"), "Next"],
            id=USER_INFO_NEXT_BUTTON_USER_INFO_ID,
            color="primary",
            disabled=True,
        ),
    )

    return page_layout(
        title="User Information",
        body=body,
        job_id=job_id,
        footer=footer,
        below=html.Div(
            id=USER_INFO_CONTENT_DIV_USER_INFO_ID, style={"display": "none"}
        ),
        step_index=1,
    )


register_page(
    __name__,
    path_template="/job/<job_id>/user-info",
    name="User Information",
    title="User Info",
    description="Enter your email address for this job.",
    dynamic=True,
    layout=layout,
)


# ============================================================================
# Helper Functions
# ============================================================================


def extract_job_id(pathname):
    match = re.match(r"^/job/([^/]+)/user-info$", pathname or "")
    return match.group(1) if match else None


def render_user_info(job_id):
    return html.Div(
        [
            html.H1("User Information"),
            html.H2(f"Job ID: {job_id}" if job_id else "No job ID provided"),
        ]
    )


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(USER_INFO_CONTENT_DIV_USER_INFO_ID, "children"),
    Input(URL_DIV_NAV_SHARED_ID, "pathname"),
)
def update_user_info_content(pathname):
    if not pathname or not pathname.endswith("/user-info"):
        raise PreventUpdate
    job_id = extract_job_id(pathname)
    return render_user_info(job_id)


# Live email validation -> toggles input valid/invalid and enables Next button
@callback(
    Output(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "valid"),
    Output(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "invalid"),
    Output(USER_INFO_NEXT_BUTTON_USER_INFO_ID, "disabled"),
    Input(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
)
def validate_email(value):
    if not value:
        return False, False, True
    is_valid = re.match(EMAIL_REGEX, value) is not None
    return (True, False, False) if is_valid else (False, True, True)


@callback(
    Output(URL_DIV_NAV_SHARED_ID, "pathname", allow_duplicate=True),
    Input(USER_INFO_NEXT_BUTTON_USER_INFO_ID, "n_clicks"),
    State(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
    State(URL_DIV_NAV_SHARED_ID, "pathname"),
    prevent_initial_call=True,
)
def go_to_upload_page(n_clicks: int | None, email: str | None, pathname: str | None):
    if not n_clicks or not pathname:
        raise PreventUpdate
    if not email or not re.match(EMAIL_REGEX, email):
        raise PreventUpdate
    if pathname.endswith("/user-info"):
        next_path = pathname.rsplit("/user-info", 1)[0] + "/data-upload"
        logging.info("Redirecting to %s", next_path)
        return next_path
    raise PreventUpdate
