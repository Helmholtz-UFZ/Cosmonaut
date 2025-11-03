# pages/user_info.py
from dash import html, register_page
import dash_bootstrap_components as dbc
from cosmonaut_app.ui.page import page_layout, progress_footer
from cosmonaut_app.constants.html_ids import (
    USER_INFO_CONTENT_DIV_USER_INFO_ID,
    USER_INFO_EMAIL_INPUT_USER_INFO_ID,
    USER_INFO_NEXT_BUTTON_USER_INFO_ID,
)


def layout(job_id=None, **kwargs):
    body = [
        html.P(
            "Enter your email to receive notifications for this job.",
            className="text-muted",
        ),
        dbc.Label("Email address", html_for=USER_INFO_EMAIL_INPUT_USER_INFO_ID, className="mt-2"),
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
        below=html.Div(id=USER_INFO_CONTENT_DIV_USER_INFO_ID, style={"display": "none"}),
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
