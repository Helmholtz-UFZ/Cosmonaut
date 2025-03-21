import base64
import glob
import json
import logging
import os
import re
import time

import dash_bootstrap_components as dbc
import dash_leaflet as dl
import geojson
import matplotlib
from dash import ctx, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions.javascript import assign
from flask import current_app
from matplotlib import pyplot as plt
from sensor_routing import sensor_routing_cli
from werkzeug.utils import secure_filename

from cosmonaut_app.classification_plot import ClassificationPlot
from cosmonaut_app.config import WEB_WORK_DIR, osm_tags_mapping
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.flask_routes import app
from cosmonaut_app.layout import (
    main_page_layout,
    not_found_page,
    stage1,
    stage2,
    stage3,
    stage4,
)
from cosmonaut_app.minio_manager import MiniIOManager
from cosmonaut_app.navigation_routing import RouteCreator
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_dead_roads,
    remove_disconnected_roads,
)
from cosmonaut_app.transformation import (
    OsmRoads,
    _get_bounds,
    get_convex_hull,
    transform_csv,
    transform_solution,
    transform_geojson,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

matplotlib.use("Agg")

# TODO Refactor the code to make it more readable and maintainable


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
    logging.info(f"Job working directory: {job_working_dir}")
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

    # with open(file_path, "r", encoding="utf-8") as file:
    #     sample = file.read(1024)
    #     file.seek(0)
    #     sniffer = csv.Sniffer()
    #     try:
    #         dialect = sniffer.sniff(sample)
    #     except csv.Error:
    #         dialect = csv.excel
    #     csv_reader = csv.reader(file, dialect)
    #     for row in csv_reader:
    #         if len(row) != amount_classes + 2:
    #             os.remove(file_path)
    #             logging.error(f"CSV must have {amount_classes + 2} columns")
    #             return (
    #                 None,
    #                 dbc.Alert(
    #                     f"CSV must have {amount_classes + 2} columns",
    #                     color="danger",
    #                     duration=5000,
    #                 ),
    #                 None,
    #             )

    logging.info("CSV File uploaded successfully")
    output_values = (
        None,
        dbc.Alert("CSV File uploaded successfully", color="success", duration=5000),
        file_path,
    )
    logging.info(f"Output values: {output_values}")
    return output_values


@app.callback(Input("file-path", "children"))
def check_file_path(file_path):
    logging.info(f"File path: {file_path}")
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

    logging.info(f"OSM triggered with file: {file_path}")

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
        logging.error(f"Error in run_osm_query: {e}")
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
                if os.path.splitext(file)[1] in ALLOWED_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    logging.info(f"Uploading file {file_path} to MinIO")
                    minio_manager.upload_file(
                        file_path,
                        f"{job_id}/{os.path.relpath(file_path, work_dir)}",
                    )
                else:
                    logging.warning(
                        f"Skipping file {file_path}: Unsupported file type."
                    )

        return dbc.Alert(
            "Allowed files and directories uploaded to MinIO",
            color="success",
            duration=5000,
        )
    except Exception as e:
        error_message = f"Uploading to MinIO failed: {str(e)}"
        logging.error(error_message)
        return dbc.Alert("Uploading to MinIO failed", color="danger", duration=5000)


# Define a JavaScript function for styling the GeoJSON features
style_handle = assign(
    """
function(feature, context){
    const {selected} = context.hideout;
    if(selected.includes(feature.id)){
        return {color: 'yellow', weight: 5}
    }
    return {color: 'red', weight: 5}
}
"""
)


@app.callback(
    Output("map", "children"),
    Input("tags-dropdown", "value"),
    State("job-id", "data"),
    Input("routing-complete", "data"),
    State("map", "children"),
    State("epsg-store", "data"),
    prevent_initial_call=True,
)
def update_map(selected_roads, job_id, routing_complete, current_children, epsg_input):
    logging.info(f"Trigger ID for geojson update: {ctx.triggered_id}")
    logging.info(f"Routing complete: {routing_complete}")

    # Remove existing GeoJSON layers
    current_children = [
        child
        for child in current_children
        if not (isinstance(child, dict) and child.get("type") == "GeoJSON")
    ]

    # Only proceed if routing is complete
    if routing_complete:
        logging.info("Routing complete detected. Updating map.")
        logging.info(job_id)

        job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
        solution_path = os.path.join(job_working_dir, "transient", "solution.json")
        transformed_solution = transform_solution(solution_path, epsg_input, 4326, True)
        logging.info(f"EPSG input: {epsg_input}")

        logging.info("Routing solution transformed")

        geojson_layer = dl.GeoJSON(
            data=transformed_solution,
            options={"style": {"color": "blue", "weight": 5}},
            id="route-geojson",
        )
        logging.info("Route GeoJSON layer created.")
        current_children.append(geojson_layer)

    # If triggered by tags-dropdown, update map with selected road types
    elif ctx.triggered_id == "tags-dropdown" and selected_roads is not None:
        logging.info("Updating map based on selected roads.")

        osm_values = [osm_tags_mapping[value] for value in selected_roads]
        osm_values = [item for sublist in osm_values for item in sublist]

        geojson_path = os.path.join(
            f"cosmonaut_app/work_dir/{job_id}/input/*_4326.geojson"
        )
        timeout = 30  # seconds
        start_time = time.time()
        while not glob.glob(geojson_path):
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    "Timed out waiting for the geojson file to be available."
                )
            time.sleep(1)

        geojson_files = glob.glob(geojson_path)
        if not geojson_files:
            raise FileNotFoundError(f"No GeoJSON file found at path: {geojson_path}")

        with open(geojson_files[0]) as f:
            data = json.load(f)

        filtered_data = {
            "type": "FeatureCollection",
            "features": [
                feature
                for feature in data["features"]
                if feature["properties"]["highway"] in osm_values
            ],
        }

        for feature in filtered_data["features"]:
            highway_type = feature["properties"]["highway"]
            name = feature["properties"].get("name") or feature["properties"].get("ref")
            tracktype = feature["properties"].get("tracktype")

            if highway_type == "track" and tracktype:
                feature["properties"]["tooltip"] = (
                    f"{name}, {highway_type}, {tracktype}"
                )
            else:
                feature["properties"]["tooltip"] = f"{name}, {highway_type}"

        geojson_layer = dl.GeoJSON(
            data=filtered_data,
            options={"style": style_handle},
            hideout=dict(selected=[]),
            id="osm-geojson",
        )
        current_children.append(geojson_layer)

    logging.info("Map updated successfully.")

    return current_children


# TODO not sure if the selected are passed currently or just highlighted for the user
@app.callback(
    Output("osm-geojson", "hideout", allow_duplicate=True),
    Input("osm-geojson", "n_clicks"),
    State("osm-geojson", "clickData"),
    State("osm-geojson", "hideout"),
    prevent_initial_call=True,
)
def toggle_select(_, clickData, hideout):
    if clickData is None or hideout is None or _ is None:
        raise PreventUpdate

    selected = hideout["selected"]
    id = clickData["id"]
    if id in selected:
        selected.remove(id)
    else:
        selected.append(id)
    return hideout


@app.callback(
    Output("plot-generation-status", "children"),
    Input("output-data-upload", "children"),
    State("file-path", "children"),
    State(
        "job-id", "data"
    ),  # Assuming the job ID is stored in a component with ID 'job-id'
)
def generate_classification_plot(upload_status, file_path, job_id):
    """
    Generate classification plots based on the uploaded data.

    Upload the plots to MinIO.
    """
    if upload_status is None:
        raise PreventUpdate

    try:
        logging.info("Generating Plots for following job_id: " + job_id)
        logging.info("Saving files to: " + os.path.join(WEB_WORK_DIR, job_id))
        # Pass the job_id to the ClassificationPlot constructor
        plot = ClassificationPlot(file_path, job_id)
        plot.generate_plots(
            [
                plt.cm.Blues,
                plt.cm.Oranges,
                plt.cm.Greens,
                plt.cm.Purples,
                plt.cm.Reds,
                plt.cm.Greys,
            ]
        )
        # TODO: FUTURE, plot the returned TileLayer on the map

        # commented out for now,
        # as for testing purposes the files dont need to be uploaded every time

        # bucket_name = "cosmic-routing"
        # manager = MiniIOManager(bucket_name)
        # for file in plot.saved_files:
        #     manager.upload_file(file, file)

        # for file in plot.saved_files:
        #     os.remove(file)

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
    Output("routing-complete", "data"),
    Input("confirm-button", "n_clicks"),
    State("routing-complete", "data"),
    State("job-id", "data"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def routing_callback(n_clicks, routing_complete, job_id):
    if n_clicks is None:
        raise PreventUpdate

    if routing_complete:
        logging.info("Setting routing complete to False first")
        return False

    # get the current job_id working directory
    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)

    # TODO make the following parameters configurable in the frontend
    total_number_of_classes = 6
    segments_number_per_class = 2
    max_distance = 50
    time_limit = 8
    optimization_objective = "d"
    max_aco_iteration = 500
    ant_no = 50
    lower_benefit_limit = 0.5

    # Run the routing directly
    sensor_routing_cli.sensor_routing(
        total_number_of_classes,
        segments_number_per_class,
        max_distance,
        job_working_dir,
        time_limit,
        optimization_objective,
        max_aco_iteration,
        ant_no,
        True,  # is_reversed
        lower_benefit_limit,
    )

    logging.info("Routing completed successfully")

    return True


@app.callback(
    Output("epsg-store", "data"),
    Input("epsg-input", "value"),
    prevent_initial_call=True,
)
def store_epsg(epsg):
    return epsg


@app.callback(
    Output("qr-code", "src"),
    Input("start-route", "n_clicks"),
    State("job-id", "data"),
    prevent_initial_call=True,
)
def update_qr_code(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate

    # Load the GeoJSON data from the solution_transformed.json file
    geojson_path = os.path.join(
        WEB_WORK_DIR, job_id, "transient", "solution_transformed.json"
    )
    with open(geojson_path) as f:
        geojson_data = json.load(f)

    # Create the RouteCreator instance with the GeoJSON data
    route_creator = RouteCreator(geojson_data)

    # Create the GPX file
    output_dir = os.path.join(WEB_WORK_DIR, job_id, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    route_creator.create_gpx(path=output_dir)

    # Upload the GPX file to MinIO and get the URL
    gpx_url = route_creator.upload_gpx(job_id=job_id)

    # Create the QR code for the GPX URL
    qr_data = route_creator.create_qr_code(gpx_url, path=output_dir)

    return qr_data["qr_code"]


# Update the clicked roads when a road is clicked
@app.callback(
    Output("clicked-roads", "data"),
    [Input("osm-geojson", "clickData")],
    [State("clicked-roads", "data")],
    prevent_initial_call=True,
)
def update_clicked_roads(clickData, clicked_roads):
    if clickData is None:
        raise PreventUpdate
    id = clickData["id"]
    if id not in clicked_roads:
        clicked_roads.append(id)
    return clicked_roads


@app.callback(
    Output("osm-geojson", "data"),
    [Input("remove-button", "n_clicks")],
    [
        State("clicked-roads", "data"),
        State("osm-geojson", "data"),
        State("job-id", "data"),
        State("epsg-store", "data"),
    ],
    prevent_initial_call=True,
)
def remove_selected(n, clicked_roads, original_data, job_id, epsg_input):
    if n is None or clicked_roads is None or original_data is None:
        raise PreventUpdate

    all_roads = original_data["features"]

    # Build the road network graph
    G = build_graph(all_roads)

    # Start by removing the clicked roads
    for road_id in clicked_roads:
        all_roads = remove_dead_roads(road_id, all_roads, G)

    # After road removals, ensure only the largest connected subnetwork remains
    largest_subnetwork = get_largest_subnetwork(G)
    all_roads = remove_disconnected_roads(G, largest_subnetwork, all_roads)

    # Filter the remaining data to include only the valid roads
    filtered_data = {
        "type": "FeatureCollection",
        "features": all_roads,
    }

    # Save the filtered data to a new GeoJSON file
    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    filtered_geojson_path = os.path.join(
        job_working_dir, "input", "osm_data_4326.geojson"
    )
    # rename the old file to keep it for debugging purposes
    os.rename(
        os.path.join(job_working_dir, "input", "osm_data_4326.geojson"),
        os.path.join(job_working_dir, "input", "osm_data_4326_old.geojson"),
    )
    with open(filtered_geojson_path, "w") as f:
        geojson.dump(filtered_data, f)
        logging.info(f"Filtered data saved to {filtered_geojson_path}")
    # transform the data to the input EPSG
    transformed_geojson = transform_geojson(filtered_geojson_path, 4326, epsg_input)
    # save the transformed data to the osm_data_epsg_input.geojson file
    transformed_geojson_path = os.path.join(
        job_working_dir, "input", f"osm_data_{epsg_input}.geojson"
    )
    with open(transformed_geojson_path, "w") as f:
        geojson.dump(transformed_geojson, f)
        logging.info(f"Transformed data saved to {transformed_geojson_path}")

    return filtered_data


@app.callback(
    Output("search-results", "children"),
    Output("job-id", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Output("redirect-interval", "disabled"),
    [Input("search-button", "n_clicks")],
    [State("search", "value")],
    prevent_initial_call=True,
)
def search_job_id(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate

    if DataBaseManager.check_existence(job_id):
        job = CosmonautJob(job_id=job_id)
        job.load()

        job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
        current_app.config["JOB_WORKING_DIR"] = job_working_dir

        return (
            dbc.Alert(
                f"Job {job_id} found and loaded successfully.",
                color="light",
                dismissable=False,
                duration=3000,
            ),
            job_id,
            f"/met/wg7/cosmonaut/job/{job_id}",
            False,
        )
    else:
        return (
            dbc.Alert(
                f"Job {job_id} not found",
                color="danger",
                dismissable=False,
                duration=3000,
            ),
            None,
            no_update,
            False,
        )


@app.callback(
    Output("url", "pathname", allow_duplicate=True),
    [Input("redirect-interval", "n_intervals")],
    prevent_initial_call=True,
)
def redirect_to_home(n_intervals):
    return "/met/wg7/cosmonaut/"


# start job when start-job button is clicked
@app.callback(
    Output("job-id", "data", allow_duplicate=True),
    Input("start-job", "n_clicks"),
    State("start-job", "n_clicks"),
    prevent_initial_call=True,
)
def start_job(n_clicks, _):
    if n_clicks is None:
        logging.debug("No clicks detected, preventing update")
        raise PreventUpdate

    # Create a new CosmonautJob instance and start the job
    logging.info("Initializing new CosmonautJob")
    job = CosmonautJob()
    job._blank_job()
    job_id = job.job_id

    try:
        job.save()
        logging.info(f"Successfully saved new job with id={job_id}")
    except Exception as e:
        logging.error(f"Failed to save job {job_id}: {str(e)}")
        raise

    # Create the working directory structure
    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    current_app.config["JOB_WORKING_DIR"] = job_working_dir

    dirs_to_create = ["", "transient/debug", "input", "plots", "output"]

    for dir_path in dirs_to_create:
        full_path = os.path.join(job_working_dir, dir_path)
        try:
            os.makedirs(full_path)
            logging.debug(f"Created directory: {full_path}")
        except OSError as e:
            logging.error(f"Failed to create directory {full_path}: {str(e)}")
            raise

    logging.info(
        f"Successfully initialized working directory structure for job {job_id}"
    )
    return job_id


@app.callback(
    Output("stage-content", "children"),
    Input("job-id", "data"),
    Input("current-stage", "data"),
    State("job-loaded-flag", "data"),
    prevent_initial_call=True,
)
def update_stage(job_id, current_stage, job_loaded_flag):
    if job_id is None:
        logging.debug("No job_id provided, returning None")
        return None

    logging.info(f"Processing job {job_id}")
    logging.debug(
        f"Input state - stage: {current_stage}, loaded_flag: {job_loaded_flag}"
    )

    try:
        job = CosmonautJob(job_id=job_id)
        loaded_stage = job.stage
        logging.debug(f"Loaded stage from job: {loaded_stage}")
    except Exception as e:
        logging.error(f"Failed to load job {job_id}: {str(e)}")
        raise

    # Check if the job was just loaded
    if current_stage is None or current_stage != loaded_stage:
        current_stage = loaded_stage
        job_loaded = True
        logging.info(f"Job {job_id} loaded with stage {current_stage}")
    else:
        job_loaded = False
        logging.debug(f"Job {job_id} already loaded")

    # Update the job_loaded_flag
    if job_loaded_flag is None:
        job_loaded_flag = job_loaded
    elif job_loaded_flag and not job_loaded:
        job_loaded_flag = False

    logging.debug(f"Updated job_loaded_flag: {job_loaded_flag}")

    # Proceed to stages based on current_stage
    try:
        if current_stage == 0:
            if not job_loaded_flag:
                logging.info(f"Job {job_id} progressing to Stage 1")
                DataBaseManager.update_column(job_id, {"stage": 1})
                return stage1(job_id)
        elif current_stage == 1:
            if not job_loaded_flag:
                logging.info(f"Job {job_id} progressing to Stage 2")
                DataBaseManager.update_column(job_id, {"stage": 2})

                # Log MinIO operations
                logging.info(f"Starting MinIO file upload for job {job_id}")
                minio_manager = MiniIOManager("cosmic-routing")
                input_dir = f"cosmonaut_app/work_dir/{job_id}/input"

                for file in os.listdir(input_dir):
                    file_path = f"{input_dir}/{file}"
                    try:
                        minio_manager.upload_file(file_path, file)
                        logging.debug(f"Successfully uploaded {file} to MinIO")
                    except Exception as e:
                        logging.error(f"Failed to upload {file} to MinIO: {str(e)}")
                        raise

                DataBaseManager.update_column(job_id, {"data_uploaded": True})
                logging.info(f"Completed MinIO uploads for job {job_id}")
                return stage2(job_id)
        elif current_stage == 2:
            if not job_loaded_flag:
                logging.info(f"Job {job_id} progressing to Stage 3")
                DataBaseManager.update_column(job_id, {"stage": 3})
                return stage3(job_id)
    except Exception as e:
        logging.error(
            f"Error processing stage {current_stage} for job {job_id}: {str(e)}"
        )
        raise

    logging.debug(f"No stage transition needed for job {job_id}")
    return None


# Add a callback to reset the job_loaded_flag when the user interacts with the job
@app.callback(
    Output("job-loaded-flag", "data"),
    Input("next-stage-button", "n_clicks"),
    State("job-loaded-flag", "data"),
)
def reset_job_loaded_flag(n_clicks, job_loaded_flag):
    if n_clicks is not None and job_loaded_flag:
        return False
    return job_loaded_flag


# TODO FIXME prev-button is buggy as hell
@app.callback(
    Output("current-stage", "data"),
    Input("next-button", "n_clicks"),
    Input("prev-button", "n_clicks"),
    State("current-stage", "data"),
)
def update_current_stage(next_clicks, prev_clicks, current_stage):
    if next_clicks is None and prev_clicks is None:
        return 0

    if next_clicks is not None:
        return current_stage + 1

    if prev_clicks is not None:
        return current_stage - 1


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
            "Disabling next button as {filename} is not uploaded, or email is not valid"
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
        logging.error(f"Job with ID {job_id} not found.")

    return ""


# add callback for toggling the collapse on small screens
@app.callback(
    Output("navbar-collapse", "is_open"),
    [Input("navbar-toggler", "n_clicks")],
    [State("navbar-collapse", "is_open")],
)
def toggle_navbar_collapse(n, is_open):
    if n:
        return not is_open
    return is_open


@app.callback(
    [Output("page-content", "children"), Output("job-page-loaded", "data")],
    [Input("url", "pathname")],
    [State("job-id", "data")],
    prevent_initial_call=True,
)
def display_page_and_update_url(pathname, job_id):
    if pathname.startswith("/met/wg7/cosmonaut/job/"):
        job_id_from_path = pathname.split("/met/wg7/cosmonaut/job/")[1]
        if DataBaseManager.check_existence(job_id_from_path):
            return stage4(job_id_from_path), True
        else:
            return not_found_page(), False
    elif pathname == "/met/wg7/cosmonaut/":
        return main_page_layout(), False
    else:
        return not_found_page(), False


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
    logging.info(f"n_clicks: {n_clicks}")
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


# Add a callback which updates the "Straßenauswahl"(tags-dropdown) into the sql database
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
        logging.info(f"Updated selected road tags with following tags: {tags}")
    except JobNotFound:
        logging.error(f"Job with ID {job_id} not found.")

    return no_update
