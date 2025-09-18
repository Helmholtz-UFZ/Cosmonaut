"""Callbacks for UI state, navigation, email, next/prev, and navbar."""

import re
import logging
from dash import no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.flask_routes import app


@app.callback(
    Output("upload-data-store", "children"),
    Input("upload-data-dcc", "contents"),
)
def store_upload_data(contents):
    return contents


@app.callback(
    Output("next-button", "disabled"),
    Input("upload-data-dcc", "filename"),
    Input("email-input", "value"),
    State("current-stage", "data"),
)
def update_next_button(filename, email, current_stage):
    email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if current_stage == 0 and email is not None and re.match(email_regex, email):
        logging.info("Email is valid - enabling next button")
        return False
    elif current_stage == 1 and filename is not None:
        logging.info("File is uploaded - enabling next button")
        return False
    else:
        logging.info(
            "Disabling next button as %s is not uploaded, or email is not valid",
            filename,
        )
        return True


@app.callback(
    Output("email-store", "data"),
    Input("email-input", "value"),
    prevent_initial_call=True,
)
def store_email(email):
    return email


@app.callback(
    Output("dummy-output", "children"),
    Input("next-button", "n_clicks"),
    State("email-store", "data"),
    State("job-id", "data"),
    prevent_initial_call=True,
)
def update_database_on_next(n_clicks, email, job_id):
    if n_clicks is None or email is None:
        raise PreventUpdate

    try:
        DataBaseManager.update_column(job_id, {"email": email})
    except JobNotFound:
        logging.error("Job with ID %s not found.", job_id)

    return ""


@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


# @app.callback(
#     [Output("page-content", "children"), Output("job-page-loaded", "data")],
#     [Input("url", "pathname")],
#     [State("job-id", "data")],
#     prevent_initial_call=True,
# )
# def display_page_and_update_url(pathname, job_id):
#     if pathname.startswith("/met/wg7/cosmonaut/job/"):
#         job_id_from_path = pathname.split("/met/wg7/cosmonaut/job/")[1]
#         if DataBaseManager.check_existence(job_id_from_path):
#             return stage4(job_id_from_path), True
#         else:
#             return not_found_page(), False
#     elif pathname == "/met/wg7/cosmonaut/":
#         return main_page_layout(), False
#     else:
#         return not_found_page(), False


@app.callback(
    Output("url", "href"),
    [Input("page-content", "children")],
    [State("url", "pathname")],
)
def update_url(content, pathname):
    if pathname.startswith("/met/wg7/cosmonaut/job/"):
        job_id_from_path = pathname.split("/met/wg7/cosmonaut/job/")[1]
        if DataBaseManager.check_existence(job_id_from_path):
            return f"/met/wg7/cosmonaut/job/{job_id_from_path}"
    return pathname


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    [Input("confirm-button", "n_clicks")],
    [State("job-id", "data")],
    prevent_initial_call=True,
)
def navigate_to_job_page(n_clicks, job_id):
    logging.info("n_clicks: %s", n_clicks)
    if n_clicks is None:
        raise PreventUpdate

    return f"/met/wg7/cosmonaut/job/{job_id}"


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    [Input("navbar-brand", "n_clicks")],
    prevent_initial_call=True,
)
def navigate_to_home(n_clicks):
    if n_clicks is None:
        raise PreventUpdate
    return "/met/wg7/cosmonaut/"


@app.callback(
    Output("none", "children"),
    Input("tags-dropdown", "value"),
    State("job-id", "data"),
    prevent_initial_call=True,
)
def update_tags_dropdown(tags, job_id):
    if tags is None:
        raise PreventUpdate

    try:
        DataBaseManager.update_column(job_id, {"selected_road_tags": tags})
        logging.info("Updated selected road tags with following tags: %s", tags)
    except JobNotFound:
        logging.error("Job with ID %s not found.", job_id)

    return no_update
