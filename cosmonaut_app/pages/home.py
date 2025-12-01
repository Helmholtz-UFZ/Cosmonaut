"""Landing page for starting a new job."""

import logging
from dash import html, register_page, callback, Input, Output
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.constants.html_ids import (
    START_JOB_BUTTON_HOME_ID,
    URL_SHARED_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    create_map,
    build_url_step,
)

register_page(
    __name__,
    path="/",
    name="Home",
    title="COSMONAUT - Start",
    description="Landing Page of COSMONAUT.",
)

card_body = [
    html.P(
        "Create a new routing job and follow the steps to upload your data, select streets, and download navigation.",
        className="text-muted mb-3",
    ),
    dbc.Button(
        [
            html.I(className="bi bi-rocket-takeoff me-2"),
            "Create new job",
        ],
        id=START_JOB_BUTTON_HOME_ID,
        color="primary",
    ),
    html.Div(
        "Or load an existing job using the search bar in the navbar.",
        className="text-muted small mt-2",
    ),
]

map = create_map()
input_container = create_card_input(card_body, title="Welcome to COSMONAUT")

layout = page_container_split_layout(map, input_container)


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
    Input(START_JOB_BUTTON_HOME_ID, "n_clicks"),
    prevent_initial_call=True,
)
def start_job(n_clicks):
    if not n_clicks:
        logging.debug("No clicks detected, preventing update")
        raise PreventUpdate

    logging.info("Initializing new CosmonautJob")
    job = CosmonautJob()

    return build_url_step("user_info", job.model.job_id)
