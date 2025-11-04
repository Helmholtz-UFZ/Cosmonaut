"""Callbacks for routing logic, QR code generation, and routing-complete state."""

import os
import time
import json
import logging
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from cosmonaut_app.config import WEB_WORK_DIR
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID,
    ROUTING_COMPLETE_STORE_SHARED_ID,
    START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
)
from sensor_routing import sensor_routing_cli
from cosmonaut_app.navigation_routing import RouteCreator
from cosmonaut_app.app import app


@app.callback(
    Output(ROUTING_COMPLETE_STORE_SHARED_ID, "data"),
    Input("confirm-button", "n_clicks"),
    State(ROUTING_COMPLETE_STORE_SHARED_ID, "data"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def routing_callback(n_clicks, routing_complete, job_id):
    if n_clicks is None:
        raise PreventUpdate

    if routing_complete:
        logging.info("Setting routing complete to False first")
        return False

    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)

    segments_number_per_class = 2
    max_distance = 50
    time_limit = 8
    optimization_objective = "d"
    max_aco_iteration = 500
    ant_no = 50
    lower_benefit_limit = 0.5

    sensor_routing_cli.sensor_routing(
        segments_number_per_class,
        max_distance,
        job_working_dir,
        time_limit,
        optimization_objective,
        max_aco_iteration,
        ant_no,
        False,
        lower_benefit_limit,
    )

    logging.info("Routing completed successfully")

    return True


@app.callback(
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
