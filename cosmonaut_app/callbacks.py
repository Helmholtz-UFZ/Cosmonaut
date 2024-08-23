import os
import re
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash import html, callback_context, dcc, no_update
from dash_extensions.javascript import assign
import dash_leaflet as dl
import dash_bootstrap_components as dbc
from flask import current_app
from werkzeug.utils import secure_filename
import base64
import csv
import json
import logging
import time
import matplotlib
import glob
from matplotlib import pyplot as plt
from cosmonaut_app.transformation import (
    OsmRoads,
    transform_csv,
    get_convex_hull,
    _get_bounds,
)
from cosmonaut_app.classification_plot import ClassificationPlot
from cosmonaut_app.minio_manager import MiniIOManager
from cosmonaut_app.config import osm_tags_mapping, WEB_WORK_DIR
from cosmonaut_app.flask_routes import app
from cosmonaut_app.navigation_routing import RouteCreator
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.layout import stage1, stage2, stage3, main_page_layout, confirm_side_bar, not_found_page

logging.basicConfig(
    format="%(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

matplotlib.use("Agg")


@app.callback(
    Output("upload-data-dcc", "contents"),
    Output("output-data-upload", "children"),
    Output("file-path", "children"),
    Input("upload-data-dcc", "contents"),
    State("upload-data-dcc", "filename"),
    prevent_initial_call=True,
)
def upload_file(contents, filename):
    """Upload a file to the server and save it in the upload directory."""
    if contents is None:
        raise PreventUpdate

    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    job_working_dir = current_app.config["JOB_WORKING_DIR"]

    filename = secure_filename(filename)
    file_path = os.path.join(job_working_dir, "upload", filename)

    with open(file_path, "wb") as f:
        f.write(decoded)

    with open(file_path, "r", encoding="utf-8") as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) != 8:
                os.remove(file_path)
                logging.error("CSV must have 8 columns")
                return (
                    None,
                    dbc.Alert("CSV must have 8 columns", color="danger", duration=5000),
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
    prevent_initial_call=True,
)
def update_map_center(file_path):
    if file_path is None:
        raise PreventUpdate

    data = transform_csv(file_path, 31468, 4326)
    bounds = _get_bounds(data)

    return dict(bounds=bounds, transition="flyTo")


@app.callback(
    Output("output-osm-query", "children"),
    Output("osm-file-path", "children"),
    Input("file-path", "children"),
)
def run_osm_query(file_path):
    if not file_path:
        raise PreventUpdate

    logging.info(f"OSM triggered with file: {file_path}")
    """Run an OSM query based on the uploaded data. Return the path to the saved OSM file."""
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
        data = transform_csv(file_path, 31468, 4326)
        convex_hull = get_convex_hull(data)

        osm = OsmRoads(convex_hull)
        osm.tags.update(osm_tags_mapping)
        osm._get_roads()

        job_working_dir = current_app.config["JOB_WORKING_DIR"]

        osm_file_path = osm.save_roads(os.path.join(job_working_dir, "osm-data"), 4326)
        osm_data = osm._osm_transform()
        osm_file_path = osm_file_path.replace("4326", "31468")
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
    State("job-status-store", "data"),
)
def upload_to_minIO(osm_file_path, job_id):
    ALLOWED_EXTENSIONS = {'.tif', '.geojson', '.json', '.csv'}
    
    if osm_file_path is None:
        raise PreventUpdate

    try:
        minio_manager = MiniIOManager("cosmic-routing")
        work_dir = f"cosmonaut_app/work_dir/{job_id}"
        
        for root, dirs, files in os.walk(work_dir):
            # Calculate the relative path from work_dir to root
            relative_path = os.path.relpath(root, work_dir)
            
            # Skip the job ID root directory itself to avoid creating an unnecessary directory
            if relative_path == ".":
                continue
            
            # Handle empty directories by creating a placeholder
            if not dirs and not files:
                minio_manager.upload_placeholder(f"{job_id}/{relative_path}/")
                continue
            
            for file in files:
                if os.path.splitext(file)[1] in ALLOWED_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    logging.info(f"Uploading file {file_path} to MinIO")
                    minio_manager.upload_file(file_path, f"{job_id}/{os.path.relpath(file_path, work_dir)}")
                else:
                    logging.warning(f"Skipping file {file_path}: Unsupported file type")
                    
        return dbc.Alert("Allowed files and directories uploaded to MinIO", color="success", duration=5000)
    except Exception as e:
        logging.error(f"Error in upload_to_minIO: {e}")
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
    [Input("tags-dropdown", "value"), Input("job-status-store", "data")],
    [State("map", "children")],
    prevent_initial_call=True,
)
def update_map(selected_roads, job_id, current_children):
    if selected_roads is None:
        return current_children

    osm_values = [osm_tags_mapping[value] for value in selected_roads]
    osm_values = [item for sublist in osm_values for item in sublist]

    # Remove any existing GeoJSON layers
    current_children = [
        child
        for child in current_children
        if not (isinstance(child, dict) and child.get("type") == "GeoJSON")
    ]

    # Load the GeoJSON data, TODO: FUTURE, load the data from the OSM file which was saved in the previous step
    geojson_path = os.path.join(
        f"cosmonaut_app/work_dir/{job_id}/osm-data/*_4326.geojson"
    )
    geojson_file = glob.glob(geojson_path)[0]
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

        # Use 'ref' if 'name' is None
        if name is None:
            name = ref

        # Add 'tracktype' to the tooltip if 'highway' is 'track'
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
    State("job-status-store", "data"),  # Assuming the job ID is stored in a component with ID 'job-id'
)
def generate_classification_plot(upload_status, file_path, job_id):
    """Generate classification plots based on the uploaded data. Upload the plots to MinIO."""
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

        # commented out for now, as for testing purposes the files dont need to be uploaded every time

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
    [Input("btn-route", "n_clicks")],
    [State("route-layer", "children")],
)
def routing_callback(n_clicks, current_layer):
    if n_clicks is None:
        return current_layer

    # Define the routes for the example test
    # TODO: FUTURE, get the routes from CAN's Navigation Algorithm
    # FIXME This is testing -> should be moved to test file in the test folder
    routes = [
        {"way": "('way', 91403181)", "start_node": 1061793565, "end_node": 1036593570},
        {"way": "('way', 922732272)", "start_node": 1036593570, "end_node": 845193413},
        {"way": "('way', 70909551)", "start_node": 845193413, "end_node": 845197359},
        {"way": "('way', 70909733)", "start_node": 845197359, "end_node": 845197431},
        {"way": "('way', 70909838)", "start_node": 845197431, "end_node": 845190677},
        {"way": "('way), 70909517)", "start_node": 845190677, "end_node": 845190684},
        {"way": "('way', 70909551)", "start_node": 845190684, "end_node": 9232344563},
        {"way": "('way', 1000189951)", "start_node": 9232344563, "end_node": 845189629},
        {"way": "('way', 54234166)", "start_node": 845189629, "end_node": 683872135},
        {"way": "('way', 89369683)", "start_node": 683872135, "end_node": 1036584699},
    ]

    geojson_path = os.path.join(
        "cosmonaut_app/download/20240424-105506_osm_data_4326.geojson"
    )

    route_creator = RouteCreator(geojson_path)
    route_layer = route_creator.create_routes_layer(routes)

    return route_layer


@app.callback(
    Output("qr-code", "src"),
    Input("btn-route", "n_clicks"),
    [State("route-layer", "children")],
)
def update_qr_code(n_clicks, current_layer):
    if n_clicks is None:
        raise PreventUpdate

    # Define the routes for the example test
    # TODO: FUTURE, get the routes from CAN's Navigation Algorithm
    # FIXME This is testing -> should be moved to test file in the test folder
    routes = [
        {"way": "('way', 91403181)", "start_node": 1061793565, "end_node": 1036593570},
        {"way": "('way', 922732272)", "start_node": 1036593570, "end_node": 845193413},
        {"way": "('way', 70909551)", "start_node": 845193413, "end_node": 845197359},
        {"way": "('way', 70909733)", "start_node": 845197359, "end_node": 845197431},
        {"way": "('way', 70909838)", "start_node": 845197431, "end_node": 845190677},
        {"way": "('way), 70909517)", "start_node": 845190677, "end_node": 845190684},
        {"way": "('way', 70909551)", "start_node": 845190684, "end_node": 9232344563},
        {"way": "('way', 1000189951)", "start_node": 9232344563, "end_node": 845189629},
        {"way": "('way', 54234166)", "start_node": 845189629, "end_node": 683872135},
        {"way": "('way', 89369683)", "start_node": 683872135, "end_node": 1036584699},
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


# Update the GeoJSON's data when the button is clicked
@app.callback(
    Output("geojson", "data"),
    [Input("remove-button", "n_clicks")],
    [State("clicked-roads", "data"), State("geojson", "data")],
    prevent_initial_call=True,
)
def remove_selected(n, clicked_roads, original_data):
    if n is None or clicked_roads is None or original_data is None:
        raise PreventUpdate
    # Filter out the clicked roads
    filtered_data = {
        "type": "FeatureCollection",
        "features": [
            feature
            for feature in original_data["features"]
            if feature["id"] not in clicked_roads
        ],
    }
    return filtered_data


# TODO: This needs to be implemented
# add callback which searches for the job_id typed into the search bar (button id = search_button, search bar id = search)
# the job_id is saved in the postgres database, the corresponding job_id is referencing also to the saved files in the minio bucket
@app.callback(
    Output("search-results", "children"),
    Output("job-status-store", "data", allow_duplicate=True),  # Store the job_id in a hidden store for further processing
    [Input("search-button", "n_clicks")],
    [State("search", "value")],
    prevent_initial_call=True,
)
def search_job_id(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate

    # Check if the job_id exists in the database
    if DataBaseManager.check_existence(job_id):
        # Load the job using the CosmonautJob class
        job = CosmonautJob(job_id=job_id)
        job.load()

        # Update the UI with job found message and save job_id to the store
        return (
            dbc.Alert(
                f"Job {job_id} found and loaded successfully.",
                color="light",
                dismissable=False,
                duration=3000,
            ),
            job_id  # Store the job_id to job-status-store
        )
    else:
        return (
            dbc.Alert(
                f"Job {job_id} not found",
                color="danger",
                dismissable=False,
                duration=3000,
            ),
            None
        )



# start job when start-job button is clicked
@app.callback(
    Output("job-status-store", "data", allow_duplicate=True),
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
    Output("progress-bar", "value"),
    Output("progress-bar", "label"),
    Input("job-status-store", "data"),
    Input("current-stage", "data"),
    State("job-loaded-flag", "data"),
)
def update_stage(job_id, current_stage, job_loaded_flag):
    if job_id is None:
        return None, 0, "0/3"

    # Load the job
    job = CosmonautJob(job_id=job_id)
    # get the current stage of the job, needed when a job is loaded from the database
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
        return stage1(job_id), 33, "1/3"

    elif current_stage == 1:
        if not job_loaded_flag:
            logging.info("Stage 2")
            DataBaseManager.update_column(job_id, {"stage": 2})
            # Upload files to MinIO
            minio_manager = MiniIOManager("cosmic-routing")
            for file in os.listdir(f"cosmonaut_app/work_dir/{job_id}/osm-data"):
                minio_manager.upload_file(
                    f"cosmonaut_app/work_dir/{job_id}/osm-data/{file}", file
                )
            DataBaseManager.update_column(job_id, {"data_uploaded": True})
        return stage2(job_id), 67, "2/3"

    elif current_stage == 2:
        if not job_loaded_flag:
            logging.info("Stage 3")
            DataBaseManager.update_column(job_id, {"stage": 3})
        return stage3(job_id), 100, "3/3"

    else:
        return None, 0, "0%"

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
    State("job-status-store", "data"),
    prevent_initial_call=True,
)
def update_database_on_next(n_clicks, email, job_id):
    if n_clicks is None or email is None:
        raise PreventUpdate

    try:
        DataBaseManager.update_column(job_id, {"email": email})
    except JobNotFound:
        print(f"Job with ID {job_id} not found.")

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

# # add a callback which triggers a new page when the confirm button is clicked (stage3)
# @app.callback(
#     Input("confirm-button", "n_clicks"),
# )

@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')],
    [State("job-status-store", "data")],
    prevent_initial_call=True
)
def display_page(pathname, job_id):
    if pathname == "/job/{}".format(job_id):
        return confirm_side_bar()
    elif pathname == "/":
        return main_page_layout()
    else:
        return not_found_page()
    
@app.callback(
    Output('url', 'pathname'),
    [Input('confirm-button', 'n_clicks')],
    [State("job-status-store", "data")],
    prevent_initial_call=True
)
def navigate_to_new_page(n_clicks, job_id):
    logging.info(f"n_clicks: {n_clicks}")
    if n_clicks is not None:
        return f'/job/{job_id}'
    return no_update