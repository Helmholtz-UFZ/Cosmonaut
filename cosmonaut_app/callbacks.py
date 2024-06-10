import os
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash import html, callback_context, dcc
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
from cosmonaut_app.db_manager import DataBaseManager

logging.basicConfig(
    filename="app.log",
    filemode="w",
    format="%(name)s - %(levelname)s - %(message)s",
    level=logging.ERROR,
)

matplotlib.use("Agg")


@app.callback(
    Output("upload-data", "contents"),
    Output("output-data-upload", "children"),
    Output("file-path", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
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
                return (
                    None,
                    html.Div(
                        [html.H5("CSV must have 8 columns")],
                        className="fade-out",
                        key=str(time.time()),
                    ),
                    None,
                )

    return (
        None,
        html.Div(
            [html.H5("File uploaded successfully")],
            className="fade-out",
            key=str(time.time()),
        ),
        file_path,
    )


@app.callback(
    Output("map", "viewport"),
    Input("file-path", "children"),
    prevent_initial_call=True,
)
def update_map_center(file_path):
    if file_path is None:
        raise PreventUpdate

    # Get the bounds of the uploaded data
    data = transform_csv(file_path, 31468, 4326)
    bounds = _get_bounds(data)

    return dict(bounds=bounds, transition="flyTo")


@app.callback(
    Output("output-osm-query", "children"),
    Output("osm-file-path", "children"),
    [Input("output-data-upload", "children")],
    [State("file-path", "children")],
)
def run_osm_query(upload_status, file_path):
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

        # Query OSM data with the initial tags
        osm = OsmRoads(convex_hull)
        osm.tags.update(osm_tags_mapping)
        osm._get_roads()

        job_working_dir = current_app.config["JOB_WORKING_DIR"]

        # Save and transform OSM data
        osm_file_path = osm.save_roads(os.path.join(job_working_dir, "osm-data"), 4326)
        osm_data = osm._osm_transform()
        osm_file_path = osm_file_path.replace("4326", "31468")
        osm_data["nodes"] = osm_data["nodes"].apply(str)
        osm_data.to_file(osm_file_path, driver="GeoJSON")

        return (
            html.Div(
                [html.H5("OSM query run successfully")],
                className="fade-out",
                key=str(time.time()),
            ),
            osm_file_path,
        )
    except Exception as e:
        if file_path is not None:
            os.remove(file_path)
        error_message = f"OSM query failed: {str(e)}"
        logging.error(error_message)
        return (
            html.Div(
                [html.H5("OSM query failed"), html.P(str(e))],
                className="fade-out",
                key=str(time.time()),
            ),
            None,
        )


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
    [Input("tags-dropdown", "value")],  # Input("osm-file-path", "children")],
    [State("map", "children")],
    prevent_initial_call=True,
)
def update_map(selected_roads, current_children):
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
        "cosmonaut_app/download/20240424-105506_osm_data_4326.geojson"
    )
    with open(geojson_path) as f:
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
)
def generate_classification_plot(upload_status, file_path):
    """Generate classification plots based on the uploaded data. Upload the plots to MinIO."""
    if upload_status is None:
        raise PreventUpdate

    try:
        plot = ClassificationPlot(file_path)
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

        for file in plot.saved_files:
            os.remove(file)

        return html.Div(
            [html.H5("Plot generated successfully")],
            className="fade-out",
            key=str(time.time()),
        )
    except Exception as e:
        error_message = f"Generating Plots failed: {str(e)}"
        logging.error(error_message)
        return html.Div(
            [html.H5("Plot generation failed"), html.P(str(e))],
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


@app.callback(
    Output("offcanvas", "is_open"),
    Input("open-offcanvas", "n_clicks"),
    [State("offcanvas", "is_open")],
)
def toggle_offcanvas(n1, is_open):
    if n1:
        return not is_open
    return is_open


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


# TODO: This needs to be implemented
# add callback which searches for the job_id typed into the search bar (button id = search_button, search bar id = search)
# the job_id is saved in the postgres database, the corresponding job_id is referencing also to the saved files in the minio bucket
@app.callback(
    Output("search-results", "children"),
    [Input("search-button", "n_clicks")],
    [State("search", "value")],
    prevent_initial_call=True,
)
def search_job_id(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate

    # search for the job_id in the postgres database
    # if the job_id is found, return the corresponding files from the minio bucket
    # if the job_id is not found, return an error message
    # use database manager to search for the job_id (check_existence)
    if DataBaseManager.check_existence(job_id):
        return dbc.Alert(
            f"Job {job_id} found",
            color="light",
            dismissable=False,
            duration=3000,
        )
    else:
        return dbc.Alert(
            f"Job {job_id} not found",
            color="light",
            dismissable=False,
            duration=3000,
        )


# start job when start-job button is clicked
@app.callback(
    Output("job-status-store", "data"),
    Input("start-job", "n_clicks"),
    State("start-job", "n_clicks"),
)
def start_job(n_clicks, _):
    if n_clicks is None:
        raise PreventUpdate

    # create a new CosmonautJob instance
    job = CosmonautJob()

    # start the job
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
)
def update_stage(job_id, current_stage):
    if job_id is None:
        return None, 0, "0%"

    if current_stage == 0:
        return (
            html.Div(
                [
                    dbc.Alert(
                        f"Started job {job_id}",
                        color="light",
                        dismissable=False,
                        duration=3000,
                    ),
                    html.H3("Upload"),
                    dcc.Upload(
                        id="upload-data",
                        accept=".csv",
                        children=html.Div(
                            [
                                "Ziehen Sie eine Datei per Drag-and-Drop oder klicken Sie, um eine Datei zum Hochladen auszuwählen."
                            ]
                        ),
                        multiple=False,
                    ),
                    html.Div(id="output-data-upload"),
                    html.Div(id="output-osm-query"),
                    html.Div(id="file-path", style={"display": "none"}),
                    html.Div(id="osm-file-path"),
                    dbc.Button(
                        "Previous Step",
                        id="prev-button",
                        className="me-auto",
                        size="lg",
                        disabled=True,
                    ),
                    dbc.Button(
                        "Next Step",
                        id="next-button",
                        className="me-auto",
                        size="lg",
                    ),
                ],
            ),
            25,
            "1/4",
        )

    elif current_stage == 1:
        return (
            html.Div(
                [
                    html.H4("Straßenauswahl"),
                    dbc.Checklist(
                        id="tags-dropdown",
                        options=[
                            {"label": tag, "value": tag}
                            for tag in osm_tags_mapping.keys()
                        ],
                        value=list(osm_tags_mapping.keys()),
                        inline=True,
                    ),
                    dbc.Button(
                        "Previous Step",
                        id="prev-button",
                        className="me-auto",
                        size="lg",
                    ),
                    dbc.Button(
                        "Next Step",
                        id="next-button",
                        className="me-auto",
                        size="lg",
                    ),
                ],
            ),
            50,
            "2/4",
        )

    else:
        return None, 0, "0%"


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
