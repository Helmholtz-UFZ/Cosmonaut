"""Landing page for creating new routing jobs.

Welcome to COSMONAUT - the starting point for creating optimized navigation routes
based on cosmic ray neutron sensor measurement locations. This page allows you to
begin a new routing job by clicking the "Create new job" button.

Each job is assigned a unique identifier that tracks your data, route selections,
and final navigation output through the entire workflow. You can also load existing
jobs using the search bar in the navigation header to continue work on a previous
routing project.

From here, you'll proceed through the workflow to provide job information, upload
membership data, select streets from OpenStreetMap, configure routing parameters,
and download your final GPX navigation file for use in the field.

NOTE: This page has no job_id context yet - the job is created on button click
and the user is redirected to the user_info page with the new job_id.
"""

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
