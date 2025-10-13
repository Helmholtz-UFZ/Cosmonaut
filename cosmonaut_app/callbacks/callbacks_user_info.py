from dash import Input, Output, State, callback, html
import re
import logging
from dash.exceptions import PreventUpdate

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


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


@callback(
    Output("user-info-content", "children"),
    Input("url", "pathname"),
)
def update_user_info_content(pathname):
    if not pathname or not pathname.endswith("/user-info"):
        raise PreventUpdate
    job_id = extract_job_id(pathname)
    return render_user_info(job_id)


# Live email validation -> toggles input valid/invalid and enables Next button
@callback(
    Output("user-info-email", "valid"),
    Output("user-info-email", "invalid"),
    Output("user-info-next", "disabled"),
    Input("user-info-email", "value"),
)
def validate_email(value):
    if not value:
        return False, False, True
    is_valid = re.match(EMAIL_REGEX, value) is not None
    return (True, False, False) if is_valid else (False, True, True)


@callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("user-info-next", "n_clicks"),
    State("user-info-email", "value"),
    State("url", "pathname"),
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
