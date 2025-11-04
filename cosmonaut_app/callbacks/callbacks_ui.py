"""Callbacks for UI state, navigation, email, next/prev, and navbar."""

import re
import logging
from dash import no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from cosmonaut_app.constants.html_ids import (
    CURRENT_STAGE_STORE_SHARED_ID,
    DUMMY_OUTPUT_DIV_SHARED_ID,
    EMAIL_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    NAVBAR_COLLAPSE_NAV_SHARED_ID,
    NAVBAR_TOGGLER_NAV_SHARED_ID,
    NONE_DIV_SHARED_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    UPLOAD_DATA_STORE_SHARED_ID,
    URL_DIV_NAV_SHARED_ID,
    USER_INFO_EMAIL_INPUT_USER_INFO_ID,
)
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.app import app


@app.callback(
    Output(UPLOAD_DATA_STORE_SHARED_ID, "children"),
    Input("upload-data-dcc", "contents"),
)
def store_upload_data(contents):
    return contents


@app.callback(
    Output("next-button", "disabled"),
    Input("upload-data-dcc", "filename"),
    Input(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
    State(CURRENT_STAGE_STORE_SHARED_ID, "data"),
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
    Output(EMAIL_STORE_SHARED_ID, "data"),
    Input(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
    prevent_initial_call=True,
)
def store_email(email):
    return email


@app.callback(
    Output(DUMMY_OUTPUT_DIV_SHARED_ID, "children"),
    Input("next-button", "n_clicks"),
    State(EMAIL_STORE_SHARED_ID, "data"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
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
    Output(NAVBAR_COLLAPSE_NAV_SHARED_ID, "is_open"),
    [Input(NAVBAR_TOGGLER_NAV_SHARED_ID, "n_clicks")],
    [State(NAVBAR_COLLAPSE_NAV_SHARED_ID, "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(
    Output(URL_DIV_NAV_SHARED_ID, "pathname", allow_duplicate=True),
    [Input("confirm-button", "n_clicks")],
    [State(JOB_ID_STORE_SHARED_ID, "data")],
    prevent_initial_call=True,
)
def navigate_to_job_page(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate
    # If still needed, direct to the next new-page step; default to user-info
    return f"/{job_id}/user-info"


@app.callback(
    Output(URL_DIV_NAV_SHARED_ID, "pathname", allow_duplicate=True),
    [Input("navbar-brand", "n_clicks")],
    prevent_initial_call=True,
)
def navigate_to_home(n_clicks):
    if n_clicks is None:
        raise PreventUpdate
    return "/met/wg7/cosmonaut/"


@app.callback(
    Output(NONE_DIV_SHARED_ID, "children"),
    Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
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
