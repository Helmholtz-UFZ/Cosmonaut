import os
import logging
import base64
import json
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from werkzeug.utils import secure_filename
from pyproj.exceptions import CRSError
from pyproj import CRS

from cosmonaut_app.config import WEB_WORK_DIR
from cosmonaut_app.minio_manager import MiniIOManager
from cosmonaut_app.transformation import _get_bounds, get_convex_hull, transform_csv
from cosmonaut_app.classification_plot import ClassificationPlot
from cosmonaut_app.flask_routes import app

import matplotlib

matplotlib.use("Agg")

# --- File Upload & Data Preparation Callbacks ---


@app.callback(
    Output("data-upload-upload", "contents"),  # reset dropzone
    Output("output-data-upload", "children"),  # status message
    Output("file-path", "children"),  # saved path
    Input("data-upload-upload", "contents"),
    State("data-upload-upload", "filename"),
    State("job-id", "data"),
    prevent_initial_call=True,
)
def upload_file(contents, filename, job_id):
    """Upload a file to the server and save it in the job working directory."""
    if not contents or not filename:
        raise PreventUpdate

    content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)

    if not job_id:
        logging.error("No job_id in store.")
        return (
            None,
            dbc.Alert("Job not initialized.", color="danger", duration=5000),
            None,
        )

    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    os.makedirs(os.path.join(job_working_dir, "input"), exist_ok=True)

    safe_name = secure_filename(filename)
    file_path = os.path.join(job_working_dir, "input", safe_name)

    with open(file_path, "wb") as f:
        f.write(decoded)

    logging.info("CSV file saved to %s", file_path)
    return (
        None,
        dbc.Toast(
            "CSV file uploaded successfully",
            header="Upload",
            icon="success",
            is_open=True,
            duration=5000,
            className="shadow",
        ),
        file_path,
    )


@app.callback(
    Output("data-upload-file-info", "children"), Input("file-path", "children")
)
def show_selected_file(file_path):
    if not file_path:
        raise PreventUpdate
    return f"Selected file: {os.path.basename(file_path)}"


@app.callback(
    Output("map", "viewport"),
    Input("file-path", "children"),
    State("data-upload-epsg", "value"),
    prevent_initial_call=True,
)
def update_map_center(file_path, epsg_input):
    if not file_path:
        raise PreventUpdate
    data = transform_csv(file_path, epsg_input, 4326)
    bounds = _get_bounds(data)
    return dict(bounds=bounds, transition="flyTo")


@app.callback(
    Output("output-osm-query", "children"),
    Output("osm-file-path", "children"),
    Input("file-path", "children"),
    State("data-upload-epsg", "value"),
    State("job-id", "data"),  # NEW: pass job id
)
def run_osm_query(file_path, epsg_input, job_id):
    if not file_path:
        raise PreventUpdate
    logging.info("OSM triggered with file: %s", file_path)

    from cosmonaut_app.transformation import OsmRoads

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
        # Ensure we have a job_id (fallback: parse from saved path)
        if not job_id and file_path:
            try:
                # .../work_dir/<job_id>/input/<file>
                job_id = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
                logging.info("Derived job_id from file_path: %s", job_id)
            except Exception:
                job_id = None
        if not job_id:
            logging.error("run_osm_query: missing job_id")
            return (
                dbc.Toast(
                    "OSM query failed: missing job ID",
                    header="OSM",
                    icon="danger",
                    is_open=True,
                    duration=6000,
                    className="shadow",
                ),
                None,
            )

        data = transform_csv(file_path, epsg_input, 4326)
        convex_hull = get_convex_hull(data)
        osm = OsmRoads(convex_hull, epsg_input=4326, epsg_output=epsg_input)
        osm.tags.update(osm_tags_mapping)
        osm._get_roads()

        # Use WEB_WORK_DIR + job_id (not Flask config)
        job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
        in_dir = os.path.join(job_working_dir, "input")
        os.makedirs(in_dir, exist_ok=True)

        # Keep original save (returns a 4326 path, legacy)
        # osm_file_path = osm.save_roads(in_dir, 4326)

        # GeoDataFrame for our new baseline/working copies
        osm_data = osm._osm_transform()
        osm_data["nodes"] = osm_data["nodes"].apply(str)

        # Persist canonical 4326 for UI (remove GeoJSON "crs" per RFC 7946)
        try:
            epsg_src = (
                int(epsg_input)
                if isinstance(epsg_input, (int, str)) and str(epsg_input).isdigit()
                else None
            )
        except Exception:
            epsg_src = None
        if osm_data.crs is None and epsg_src:
            osm_data = osm_data.set_crs(epsg=epsg_src, allow_override=True)
        osm_4326 = (
            osm_data.to_crs(epsg=4326)
            if (osm_data.crs and osm_data.crs.to_epsg() != 4326)
            else osm_data
        )

        raw_4326 = os.path.join(in_dir, "osm_data_raw_4326.geojson")
        work_4326 = os.path.join(in_dir, "osm_data_work_4326.geojson")
        osm_4326_json = json.loads(osm_4326.to_json())
        osm_4326_json.pop("crs", None)
        with open(raw_4326, "w", encoding="utf-8") as f:
            json.dump(osm_4326_json, f, ensure_ascii=False)
        with open(work_4326, "w", encoding="utf-8") as f:
            json.dump(osm_4326_json, f, ensure_ascii=False)

        # EPSG-specific export required by later steps (this may include a CRS)
        try:
            epsg_out = int(epsg_input)
        except Exception:
            epsg_out = None
        if epsg_out:
            if epsg_out == 4326:
                # If requested out is 4326, persist explicitly as well (ok to contain no CRS)
                with open(
                    os.path.join(in_dir, f"osm_data_{epsg_out}.geojson"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(osm_4326_json, f, ensure_ascii=False)
            else:
                osm_proj = osm_4326.to_crs(epsg=epsg_out)
                osm_proj.to_file(
                    os.path.join(in_dir, f"osm_data_{epsg_out}.geojson"),
                    driver="GeoJSON",
                )

        logging.info(
            "OSM query successful (job %s). Baseline and working files written.", job_id
        )
        return (
            dbc.Toast(
                "OSM query successful",
                header="OSM",
                icon="success",
                is_open=True,
                duration=5000,
                className="shadow",
            ),
            work_4326,  # return working file path (anything truthy triggers next step)
        )
    except Exception as e:
        logging.error("Error in run_osm_query: %s", e, exc_info=True)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return (
            dbc.Toast(
                "OSM query failed",
                header="OSM",
                icon="danger",
                is_open=True,
                duration=5000,
                className="shadow",
            ),
            None,
        )


@app.callback(
    Output("output-minIO-status", "children"),
    Input("osm-file-path", "children"),
    State("job-id", "data"),
)
def upload_to_minIO(osm_file_path, job_id):
    ALLOWED_EXTENSIONS = {".tif", ".geojson", ".json", ".csv", ".gpx"}
    if not osm_file_path:
        raise PreventUpdate
    try:
        minio_manager = MiniIOManager("cosmic-routing")
        work_dir = f"cosmonaut_app/work_dir/{job_id}"

        for root, dirs, files in os.walk(work_dir):
            relative_path = os.path.relpath(root, work_dir)
            if relative_path == ".":
                continue
            if not dirs and not files:
                minio_manager.upload_placeholder(f"{job_id}/{relative_path}/")
                continue
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.splitext(file)[1] in ALLOWED_EXTENSIONS:
                    minio_manager.upload_file(
                        file_path, f"{job_id}/{os.path.relpath(file_path, work_dir)}"
                    )
        return dbc.Toast(
            "Allowed files and directories uploaded to MinIO",
            header="MinIO",
            icon="success",
            is_open=True,
            duration=5000,
            className="shadow",
        )
    except Exception as e:
        logging.error("Uploading to MinIO failed: %s", e, exc_info=True)
        return dbc.Toast(
            "Uploading to MinIO failed",
            header="MinIO",
            icon="danger",
            is_open=True,
            duration=5000,
            className="shadow",
        )


@app.callback(
    Output("plot-generation-status", "children"),
    Input("output-data-upload", "children"),
    State("file-path", "children"),
    State("job-id", "data"),
    State("epsg-store", "data"),
    prevent_initial_call=True,
)
def generate_classification_plot(upload_status, file_path, job_id, src_epsg):
    if upload_status is None:
        raise PreventUpdate
    if src_epsg is None:
        return dbc.Toast(
            "Source EPSG is not set. Please provide a valid EPSG code.",
            header="Plots",
            icon="danger",
            is_open=True,
            duration=5000,
            className="shadow",
        )
    try:
        plot = ClassificationPlot(file_path, job_id, src_epsg=f"EPSG:{src_epsg}")
        plot.generate_plots()
        return dbc.Toast(
            "Plot generated successfully",
            header="Plots",
            icon="success",
            is_open=True,
            duration=5000,
            className="shadow",
        )
    except Exception as e:
        logging.error("Generating Plots failed: %s", e)
        return dbc.Toast(
            "Generating Plots failed",
            header="Plots",
            icon="danger",
            is_open=True,
            duration=5000,
            className="shadow",
        )


@app.callback(
    Output("data-upload-epsg-helper", "children"),
    Output("data-upload-epsg", "valid"),
    Output("data-upload-epsg", "invalid"),
    Output("epsg-store", "data"),
    Input("data-upload-epsg", "value"),
)
def validate_and_store_epsg(epsg):
    # Reset when empty/cleared
    if epsg in (None, "", []):
        return ("", False, False, None)

    # Coerce to int safely
    try:
        if isinstance(epsg, str) and epsg.upper().startswith("EPSG:"):
            epsg = epsg[5:]
        epsg = int(epsg)
    except (TypeError, ValueError):
        return ("Invalid EPSG code", False, True, None)

    # Validate with pyproj
    try:
        CRS.from_epsg(epsg)
        return ("EPSG accepted", True, False, epsg)
    except (CRSError, ValueError, TypeError):
        return ("Invalid EPSG code", False, True, None)


# Enable/disable controls based on store
@app.callback(
    Output("data-upload-upload", "disabled"),
    Input("epsg-store", "data"),
)
def toggle_upload_disabled(epsg):
    return epsg is None


@app.callback(
    Output("data-upload-next", "disabled"),
    Input("file-path", "children"),
    Input("epsg-store", "data"),
)
def enable_next(file_path, epsg):
    return not (file_path and epsg)


# Navigation: prev/next (SPA)
@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("data-upload-next", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def go_to_street_selection(n_clicks, pathname):
    if not n_clicks or not pathname or not pathname.endswith("/data-upload"):
        raise PreventUpdate
    return pathname.rsplit("/data-upload", 1)[0] + "/street-selection"


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    Input("data-upload-prev", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def back_to_user_info(n_clicks, pathname):
    if not n_clicks or not pathname or not pathname.endswith("/data-upload"):
        raise PreventUpdate
    return pathname.rsplit("/data-upload", 1)[0] + "/user-info"
