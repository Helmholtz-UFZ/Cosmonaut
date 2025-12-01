"""Route & Download page: show route, QR code, and GPX download."""

import logging
from dash import html, register_page, callback, Input, Output, State, dcc
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID,
    START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
)
from cosmonaut_app.layout import (
    create_map,
    page_container_split_layout,
    create_card_input,
    progress_footer,
    build_url_step,
)

register_page(
    __name__,
    path_template="/job/<job_id>/route-download",
    name="Route & Download",
    title="Route Download",
    description="View the calculated route and download the GPX file.",
    dynamic=True,
)


def layout(job_id):
    job = CosmonautJob(job_id=job_id)
    logging.info(f"Route & Download layout called with job_id={job_id}")
    card_body = [
        html.P(
            "Bitte haben Sie Geduld, bis die Route berechnet ist.",
            style={"margin-bottom": "0.5rem", "font-size": "1.2rem"},
        ),
        html.P(
            "Wenn der 'Start Route'-Button gedrückt wird, erscheint ein QR-Code "
            "zum Download der GPX-Datei der finalen Route.",
            style={"margin-bottom": "1rem", "font-size": "1.2rem"},
        ),
        dbc.Button(
            "Start Route",
            id=START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
            color="success",
            className="me-2",
            n_clicks=0,
        ),
        html.Div(
            html.Img(
                id=QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID,
                style={"margin-top": "1rem", "max-width": "100%"},
            ),
            style={"textAlign": "center"},
        ),
        dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id),
    ]

    routing_params_path = build_url_step("routing_params", job_id)

    footer = progress_footer(
        prev_url=routing_params_path,
        next_url=None,
    )

    map = create_map(job=job)

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID, "src"),
    Input(START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def update_qr_code(n_clicks, job_id):
    logging.info(f"Generating QR code for job_id={job_id} on click {n_clicks}")
    if n_clicks is None:
        raise PreventUpdate
    job = CosmonautJob(job_id=job_id)
    return job.create_qr_code_routing()
