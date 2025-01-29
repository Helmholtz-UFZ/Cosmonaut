import base64
import csv
import glob
import json
import logging
import os
import re
import time

import dash_bootstrap_components as dbc
import dash_leaflet as dl
import matplotlib
from dash import no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions.javascript import assign
from flask import current_app
from matplotlib import pyplot as plt

# from sensor_routing import sensor_routing_cli
from werkzeug.utils import secure_filename

# from cosmonaut_app.celery_config import celery
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
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

matplotlib.use("Agg")


@app.callback(
    Output("upload-data-dcc", "contents"),
    Output("output-data-upload", "children"),
    Output("file-path", "children"),
    Input("upload-data-dcc", "contents"),
    State("upload-data-dcc", "filename"),
    State("amount-classes-input", "value"),
    prevent_initial_call=True,
)
def upload_file(contents, filename, amount_classes):
    """Upload a file to the server and save it in the upload directory."""
    if contents is None or filename is None or amount_classes is None:
        raise PreventUpdate

    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    job_working_dir = WEB_WORK_DIR
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

    upload_dir = os.path.join(job_working_dir, "upload")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    filename = secure_filename(filename)
    file_path = os.path.join(job_working_dir, "upload", filename)

    with open(file_path, "wb") as f:
        f.write(decoded)

    with open(file_path, "r", encoding="utf-8") as file:
        sample = file.read(1024)
        file.seek(0)
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(sample)
        except csv.Error:
            dialect = csv.excel
        csv_reader = csv.reader(file, dialect)
        for row in csv_reader:
            if len(row) != amount_classes + 2:
                os.remove(file_path)
                logging.error(f"CSV must have {amount_classes + 2} columns")
                return (
                    None,
                    dbc.Alert(
                        f"CSV must have {amount_classes + 2} columns",
                        color="danger",
                        duration=5000,
                    ),
                    None,
                )

    logging.info("File uploaded successfully")
    output_values = (
        None,
        dbc.Alert("File uploaded successfully", color="success", duration=5000),
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

    # TODO: EPSG needs to be respected later on
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

        osm = OsmRoads(convex_hull)
        osm.tags.update(osm_tags_mapping)
        osm._get_roads()

        job_working_dir = current_app.config["JOB_WORKING_DIR"]

        osm_file_path = osm.save_roads(os.path.join(job_working_dir, "osm-data"), 4326)
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
    ALLOWED_EXTENSIONS = {".tif", ".geojson", ".json", ".csv"}

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
    Input("job-id", "data"),
    State("map", "children"),
    prevent_initial_call=True,
)
def update_map_with_geojson(selected_roads, job_id, current_children):
    """
    Update the map with GeoJSON layers based on the selected roads and job ID.

    Parameters:
    selected_roads (list): List of selected road tags from the dropdown.
    job_id (str): The job ID used to locate the GeoJSON file.
    current_children (list): The current children elements of the map.

    Returns:
    list: Updated list of children elements for the map.
    """
    if selected_roads is None:
        return current_children

    # logging.info(f"geojson tags: {selected_roads}"),

    osm_values = [osm_tags_mapping[value] for value in selected_roads]
    osm_values = [item for sublist in osm_values for item in sublist]

    current_children = [
        child
        for child in current_children
        if not (isinstance(child, dict) and child.get("type") == "GeoJSON")
    ]

    geojson_path = os.path.join(
        f"cosmonaut_app/work_dir/{job_id}/osm-data/*_4326.geojson"
    )

    logging.info(f"Geojson Path: {geojson_path}")

    timeout = 30  # seconds
    start_time = time.time()
    while not glob.glob(geojson_path):
        logging.info(f"Waiting for geojson file at path: {geojson_path}")
        if time.time() - start_time > timeout:
            raise TimeoutError(
                "Timed out waiting for the geojson file to be available."
            )
        time.sleep(1)

    geojson_files = glob.glob(geojson_path)
    if not geojson_files:
        raise FileNotFoundError(f"No GeoJSON file found at path: {geojson_path}")

    geojson_file = geojson_files[0]
    logging.info(f"Geojson file found: {geojson_file}")
    with open(geojson_file) as f:
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
        name = feature["properties"].get("name")
        ref = feature["properties"].get("ref")
        tracktype = feature["properties"].get("tracktype")

        if name is None:
            name = ref

        if highway_type == "track" and tracktype is not None:
            feature["properties"]["tooltip"] = f"{name}, {highway_type}, {tracktype}"
        else:
            feature["properties"]["tooltip"] = f"{name}, {highway_type}"

    geojson_layer = dl.GeoJSON(
        data=filtered_data,
        options={"style": style_handle},
        hideout=dict(selected=[]),
        id="geojson",
    )

    current_children.extend([geojson_layer])

    return current_children


@app.callback(
    Output("geojson", "hideout", allow_duplicate=True),
    Input("geojson", "n_clicks"),
    State("geojson", "clickData"),
    State("geojson", "hideout"),
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
    Output("route-layer", "children"),
    Input("job-page-loaded", "data"),
    [State("route-layer", "children"), State("osm-file-path", "children")],
    prevent_initial_call=True,
)
def routing_callback(job_page_loaded, current_layer, osm_file_path):
    if not job_page_loaded:
        return current_layer

    time.sleep(1)

    # total_number_of_classes = 9
    # segments_number_per_class = 2
    # max_distance = 50
    # class_data = (
    #     "Mueglitz_extended_9Cluster_EPSG25832-2.csv"  # Update this path as needed
    # )
    # time_limit = 8
    # optimization_objective = "d"
    # max_aco_iteration = 500
    # ant_no = 50
    # point_mapping_output = "pm_output.json"
    # benefit_calculation_output_benefit = "bc_benefits_output.json"
    # benefit_calculation_output_top_benefit = "bc_top_benefits_output.json"
    # path_finding_output = "pf_output.json"
    solution_path = "solution.json"

    # run_sensor_routing.delay(
    #     total_number_of_classes,
    #     segments_number_per_class,
    #     max_distance,
    #     osm_file_path,
    #     class_data,
    #     time_limit,
    #     optimization_objective,
    #     max_aco_iteration,
    #     ant_no,
    #     point_mapping_output,
    #     benefit_calculation_output_benefit,
    #     benefit_calculation_output_top_benefit,
    #     path_finding_output,
    #     solution_path,
    # )

    # @celery.task
    # def run_sensor_routing(
    #     total_number_of_classes,
    #     segments_number_per_class,
    #     max_distance,
    #     osm_file_path,
    #     class_data,
    #     time_limit,
    #     optimization_objective,
    #     max_aco_iteration,
    #     ant_no,
    #     point_mapping_output,
    #     benefit_calculation_output_benefit,
    #     benefit_calculation_output_top_benefit,
    #     path_finding_output,
    #     solution_path,
    # ):
    #     sensor_routing_cli.sensor_routing(
    #         total_number_of_classes,
    #         segments_number_per_class,
    #         max_distance,
    #         osm_file_path,
    #         class_data,
    #         time_limit,
    #         optimization_objective,
    #         max_aco_iteration,
    #         ant_no,
    #         point_mapping_output,
    #         benefit_calculation_output_benefit,
    #         benefit_calculation_output_top_benefit,
    #         path_finding_output,
    #         solution_path,
    #     )

    with open(solution_path) as f:
        data = json.load(f)

    geojson_path = osm_file_path

    route_creator = RouteCreator(geojson_path)
    route_layer = route_creator.create_route_layer(data)

    return route_layer


@app.callback(
    Output("qr-code", "src"),
    Input("start-route", "n_clicks"),
    [State("route-layer", "children")],
    prevent_initial_call=True,
)
def update_qr_code(n_clicks, current_layer):
    if n_clicks is None:
        raise PreventUpdate

    # Define the routes for the example test
    # TODO: FUTURE, get the routes from CAN's Navigation Algorithm
    # FIXME This is testing -> should be moved to test file in the test folder
    routes = [
        {
            "way": "('way', 91403181)",
            "start_node": 1061793565,
            "end_node": 1036593570,
        },
        {
            "way": "('way', 922732272)",
            "start_node": 1036593570,
            "end_node": 845193413,
        },
        {
            "way": "('way', 70909551)",
            "start_node": 845193413,
            "end_node": 845197359,
        },
        {
            "way": "('way', 70909733)",
            "start_node": 845197359,
            "end_node": 845197431,
        },
        {
            "way": "('way', 70909838)",
            "start_node": 845197431,
            "end_node": 845190677,
        },
        {
            "way": "('way), 70909517)",
            "start_node": 845190677,
            "end_node": 845190684,
        },
        {
            "way": "('way', 70909551)",
            "start_node": 845190684,
            "end_node": 9232344563,
        },
        {
            "way": "('way', 1000189951)",
            "start_node": 9232344563,
            "end_node": 845189629,
        },
        {
            "way": "('way', 54234166)",
            "start_node": 845189629,
            "end_node": 683872135,
        },
        {
            "way": "('way', 89369683)",
            "start_node": 683872135,
            "end_node": 1036584699,
        },
    ]

    geojson_path = os.path.join(
        "cosmonaut_app/download/20240424-105506_osm_data_4326.geojson"
    )

    route_creator = RouteCreator(geojson_path)

    route_creator.create_gpx(routes)
    gpx_url = route_creator.upload_gpx()
    qr_data_url = route_creator.create_qr_code(gpx_url)
    route_creator.delete_gpx()

    return qr_data_url


# Update the clicked roads when a road is clicked
@app.callback(
    Output("clicked-roads", "data"),
    [Input("geojson", "clickData")],
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
    Output("geojson", "data"),
    [Input("remove-button", "n_clicks")],
    [State("clicked-roads", "data"), State("geojson", "data")],
    prevent_initial_call=True,
)
def remove_selected(n, clicked_roads, original_data):
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
        raise PreventUpdate

    # create a new CosmonautJob instance and start the job
    job = CosmonautJob()
    job._blank_job()
    job_id = job.job_id
    job.save()

    # create the working directory for the job
    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    current_app.config["JOB_WORKING_DIR"] = job_working_dir
    os.makedirs(job_working_dir)
    os.makedirs(os.path.join(job_working_dir, "upload"))
    os.makedirs(os.path.join(job_working_dir, "osm-data"))
    os.makedirs(os.path.join(job_working_dir, "plots"))

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
        return None

    job = CosmonautJob(job_id=job_id)
    loaded_stage = job.stage

    # Check if the job was just loaded
    if current_stage is None or current_stage != loaded_stage:
        current_stage = loaded_stage
        job_loaded = True
    else:
        job_loaded = False

    # Update the job_loaded_flag
    if job_loaded_flag is None:
        job_loaded_flag = job_loaded
    elif job_loaded_flag and not job_loaded:
        job_loaded_flag = False

    # Proceed to stages based on current_stage
    if current_stage == 0:
        if not job_loaded_flag:
            logging.info("Stage 1")
            DataBaseManager.update_column(job_id, {"stage": 1})
        return stage1(job_id)

    elif current_stage == 1:
        if not job_loaded_flag:
            logging.info("Stage 2")
            DataBaseManager.update_column(job_id, {"stage": 2})

            minio_manager = MiniIOManager("cosmic-routing")
            for file in os.listdir(f"cosmonaut_app/work_dir/{job_id}/osm-data"):
                minio_manager.upload_file(
                    f"cosmonaut_app/work_dir/{job_id}/osm-data/{file}", file
                )
            DataBaseManager.update_column(job_id, {"data_uploaded": True})
        return stage2(job_id)

    elif current_stage == 2:
        if not job_loaded_flag:
            logging.info("Stage 3")
            DataBaseManager.update_column(job_id, {"stage": 3})
        return stage3(job_id)

    else:
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
        return False
    elif current_stage == 1 and filename is not None:
        return False
    else:
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
    # TODO: Here the Route Calculation should be triggered
    # for now, just create a random route
    # Input: the OSM data with the tags defined by the user
    # Output: the route as a GeoJSON file
    #
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

    # logging.info(f"sql tags: {tags}")

    try:
        DataBaseManager.update_column(job_id, {"selected_road_tags": tags})
    except JobNotFound:
        logging.error(f"Job with ID {job_id} not found.")

    return no_update
