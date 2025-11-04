"""Route & Download page: show route, QR code, and GPX download."""

import os
import time
import json
import logging
from dash import html, register_page, callback, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.ui.page import page_layout
from cosmonaut_app.config import WEB_WORK_DIR
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID,
    START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
)
from cosmonaut_app.navigation_routing import RouteCreator

register_page(
    __name__,
    path_template="/job/<job_id>/route-download",
    name="Route & Download",
    title="Route Download",
    description="View the calculated route and download the GPX file.",
    dynamic=True,
)


def layout(job_id=None, **kwargs):
    body = [
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
    ]
    return page_layout("Route & Download", body, job_id=job_id, step_index=5)


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
    if n_clicks is None:
        raise PreventUpdate
    geojson_path = os.path.join(
        WEB_WORK_DIR, job_id, "transient", "solution_transformed.json"
    )
    with open(geojson_path, encoding="utf-8") as f:
        geojson_data = json.load(f)
    route_creator = RouteCreator(geojson_data)
    output_dir = os.path.join(WEB_WORK_DIR, job_id, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    gpx_filename = f"{job_id}_route_{time.strftime('%Y%m%d')}.gpx"
    full_path = os.path.join(output_dir, gpx_filename)
    route_creator.create_gpx(filename=gpx_filename, path=output_dir)
    logging.debug("GPX file created at %s", full_path)
    if not os.path.exists(full_path):
        logging.error("GPX file does not exist: %s", full_path)
        raise FileNotFoundError(f"GPX file not found: {full_path}")
    gpx_url = route_creator.upload_gpx(filename=gpx_filename, job_id=job_id)
    qr_data = route_creator.create_qr_code(gpx_url, path=output_dir)
    return qr_data["qr_code"]
