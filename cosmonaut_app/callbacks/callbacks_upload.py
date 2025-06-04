"""Callbacks for file upload, OSM query, MinIO upload, EPSG validation, and plot generation."""

import base64
import os
import logging
import time
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from werkzeug.utils import secure_filename
from flask import current_app
from pyproj.exceptions import CRSError
from pyproj import CRS

from cosmonaut_app.config import WEB_WORK_DIR
from cosmonaut_app.minio_manager import MiniIOManager
from cosmonaut_app.transformation import (
    _get_bounds,
    get_convex_hull,
    transform_csv,
)
from cosmonaut_app.classification_plot import ClassificationPlot

import matplotlib

matplotlib.use("Agg")

# --- File Upload & Data Preparation Callbacks ---

from cosmonaut_app.flask_routes import app


@app.callback(
    Output("upload-data-dcc", "contents"),
    Output("output-data-upload", "children"),
    Output("file-path", "children"),
    Input("upload-data-dcc", "contents"),
    State("upload-data-dcc", "filename"),
    State("job-id", "data"),
    prevent_initial_call=True,
)
def upload_file(contents, filename, job_id):
    """Upload a file to the server and save it in the upload directory."""
    if contents is None or filename is None:
        raise PreventUpdate

    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    logging.info("Job working directory: %s", job_working_dir)
    if not job_working_dir:
        logging.error("Job working directory is not set")
        return (
            None,
            dbc.Alert(
                "Job working directory is not set",
                color="danger",
                duration=5000,
            ),
            None,
        )

    input_dir = os.path.join(job_working_dir, "input")
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)

    filename = secure_filename(filename)
    file_path = os.path.join(job_working_dir, "input", filename)

    with open(file_path, "wb") as f:
        f.write(decoded)

    logging.info("CSV File uploaded successfully")
    output_values = (
        None,
        dbc.Alert("CSV File uploaded successfully", color="success", duration=5000),
        file_path,
    )
    logging.info("Output values: %s", output_values)
    return output_values


@app.callback(Input("file-path", "children"))
def check_file_path(file_path):
    logging.info("File path: %s", file_path)
    return None


@app.callback(
    Output("map", "viewport"),
    Input("file-path", "children"),
    State("epsg-input", "value"),
    prevent_initial_call=True,
)
def update_map_center(file_path, epsg_input):
    if file_path is None:
        raise PreventUpdate

    data = transform_csv(file_path, epsg_input, 4326)
    bounds = _get_bounds(data)

    return dict(bounds=bounds, transition="flyTo")


@app.callback(
    Output("output-osm-query", "children"),
    Output("osm-file-path", "children"),
    Input("file-path", "children"),
    State("epsg-input", "value"),
)
def run_osm_query(file_path, epsg_input):
    if not file_path:
        raise PreventUpdate

    logging.info("OSM triggered with file: %s", file_path)

    osm_tags_mapping = {
        "highway": [
            "motorway",
            "primary",
            "secondary",
            "tertiary",
            "unclassified",
            "residential",
            "living_street",
            "track",
        ]
    }

    try:
        data = transform_csv(file_path, epsg_input, 4326)
        convex_hull = get_convex_hull(data)

        from cosmonaut_app.transformation import OsmRoads

        osm = OsmRoads(convex_hull, epsg_input=4326, epsg_output=epsg_input)
        osm.tags.update(osm_tags_mapping)
        osm._get_roads()

        job_working_dir = current_app.config["JOB_WORKING_DIR"]

        osm_file_path = osm.save_roads(os.path.join(job_working_dir, "input"), 4326)
        osm_data = osm._osm_transform()
        osm_file_path = osm_file_path.replace("4326", str(epsg_input))
        osm_data["nodes"] = osm_data["nodes"].apply(str)
        osm_data.to_file(osm_file_path, driver="GeoJSON")
        logging.info("OSM query successful")
        return (
            dbc.Alert("OSM query successful", color="success", duration=5000),
            osm_file_path,
        )
    except Exception as e:
        logging.error("Error in run_osm_query: %s", e)
        if file_path is not None:
            os.remove(file_path)
        error_message = f"OSM query failed: {str(e)}"
        logging.error(error_message)
        return (
            dbc.Alert("OSM query failed", color="danger", duration=5000),
            None,
        )


@app.callback(
    Output("output-minIO-status", "children"),
    Input("osm-file-path", "children"),
    State("job-id", "data"),
)
def upload_to_minIO(osm_file_path, job_id):
    ALLOWED_EXTENSIONS = {".tif", ".geojson", ".json", ".csv", ".gpx"}

    if osm_file_path is None:
        logging.error("OSM file path is None. Preventing update.")
        raise PreventUpdate

    try:
        logging.info("Initializing MinIO manager for bucket 'cosmic-routing'")
        minio_manager = MiniIOManager("cosmic-routing")
        work_dir = f"cosmonaut_app/work_dir/{job_id}"

        for root, dirs, files in os.walk(work_dir):
            logging.info("Walking directory: %s", root)
            relative_path = os.path.relpath(root, work_dir)
            logging.info("Relative path: %s", relative_path)

            if relative_path == ".":
                continue

            if not dirs and not files:
                logging.info(
                    "Creating placeholder for empty directory: %s", relative_path
                )
                minio_manager.upload_placeholder(f"{job_id}/{relative_path}/")
                continue

            for file in files:
                file_path = os.path.join(root, file)
                logging.info("Found file: %s", file_path)
                if os.path.splitext(file)[1] in ALLOWED_EXTENSIONS:
                    logging.info("Uploading file %s to MinIO", file_path)
                    minio_manager.upload_file(
                        file_path,
                        f"{job_id}/{os.path.relpath(file_path, work_dir)}",
                    )
                else:
                    logging.warning(
                        "Skipping file %s: Unsupported file type.", file_path
                    )

        return dbc.Alert(
            "Allowed files and directories uploaded to MinIO",
            color="success",
            duration=5000,
        )
    except Exception as e:
        error_message = f"Uploading to MinIO failed: {str(e)}"
        logging.error(error_message, exc_info=True)
        return dbc.Alert("Uploading to MinIO failed", color="danger", duration=5000)


@app.callback(
    Output("plot-generation-status", "children"),
    Input("output-data-upload", "children"),
    State("file-path", "children"),
    State("job-id", "data"),
    State("epsg-store", "data"),
    prevent_initial_call=True,
)
def generate_classification_plot(upload_status, file_path, job_id, src_epsg):
    """
    Generate classification plots based on the uploaded data.

    Upload the plots to MinIO.
    """
    if upload_status is None:
        raise PreventUpdate

    if src_epsg is None:
        logging.error("Source EPSG is not set. Cannot proceed.")
        return dbc.Alert(
            "Source EPSG is not set. Please provide a valid EPSG code.",
            color="danger",
            className="fade-out",
            key=str(time.time()),
        )

    try:
        logging.info(
            "Generating Plots for job_id: %s with source EPSG: %s", job_id, src_epsg
        )
        logging.info("Saving files to: %s", os.path.join(WEB_WORK_DIR, job_id))

        plot = ClassificationPlot(file_path, job_id, src_epsg=f"EPSG:{src_epsg}")
        plot.generate_plots()

        return dbc.Alert(
            "Plot generated successfully",
            color="success",
            className="fade-out",
            key=str(time.time()),
        )
    except Exception as e:
        error_message = f"Generating Plots failed: {str(e)}"
        logging.error(error_message)
        return dbc.Alert(
            "Generating Plots failed",
            color="danger",
            className="fade-out",
            key=str(time.time()),
        )


@app.callback(
    [
        Output("epsg-feedback", "children"),
        Output("epsg-feedback", "style"),
        Output("epsg-store", "data"),
    ],
    [
        Input("epsg-input", "value"),
        State("epsg-store", "data"),
    ],
    prevent_initial_call=True,
)
def validate_and_store_epsg(epsg, current_epsg):
    if epsg is None:
        raise PreventUpdate

    try:
        if isinstance(epsg, str) and epsg.upper().startswith("EPSG:"):
            epsg = epsg[5:]
        epsg = int(epsg)
    except ValueError:
        logging.warning("Invalid EPSG value (not an integer): %s", epsg)
        return (
            "❌ Ungültiger EPSG-Code",
            {"color": "red", "margin-left": "10px"},
            None,
        )

    try:
        CRS.from_epsg(epsg)
        logging.info("Storing valid EPSG value: %s", epsg)
        return (
            "✔️ EPSG-Code akzeptiert",
            {"color": "green", "margin-left": "10px"},
            epsg,
        )
    except (CRSError, ValueError, TypeError):
        logging.warning("Invalid EPSG value: %s", epsg)
        return (
            "❌ Ungültiger EPSG-Code",
            {"color": "red", "margin-left": "10px"},
            None,
        )


@app.callback(
    Output("upload-button", "disabled"),
    Input("epsg-store", "data"),
)
def toggle_upload_button(epsg):
    return epsg is None
