from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os
from dash import html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from werkzeug.utils import secure_filename
import base64
import csv
from transformation import OsmRoads, transform_csv, get_convex_hull, _get_bounds
import time
import dash_leaflet as dl
from matplotlib import pyplot as plt
from classification_plot import ClassificationPlot
from minio_manager import MiniIOManager
from config import osm_tags_mapping
import matplotlib
from flask_routes import UPLOAD_FOLDER, DOWNLOAD_FOLDER, uploaded_files, file_link, app
import logging
from navigation_routing import RouteCreator

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

    filename = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

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
    prevent_initial_call=True
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
    [State("file-path", "children"), State("tags-dropdown", "value")],
)
def run_osm_query(upload_status, file_path, selected_tags):
    """Run an OSM query based on the uploaded data and the selected tags. Return the path to the saved OSM file."""
    osm_values = [osm_tags_mapping[value] for value in selected_tags]
    osm_values = [item for sublist in osm_values for item in sublist]
    if upload_status is None or not selected_tags or file_path is None:
        raise PreventUpdate
    try:
        data = transform_csv(file_path, 31468, 4326)
        convex_hull = get_convex_hull(data)

        # Modify the tags based on the selected tags dropdown
        additional_tags = {"highway": osm_values}

        # Query OSM data with the modified tags
        osm = OsmRoads(convex_hull)
        osm.tags.update(additional_tags)
        osm._get_roads() # additional_tags=additional_tags)

        # Save and transform OSM data
        osm_file_path = osm.save_roads(DOWNLOAD_FOLDER, 4326)
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


# TODO: Not needed in the future.
@app.callback(
    Output("points", "children"),
    Input("output-data-upload", "children"),
    State("file-path", "children"),
)
def show_points(upload_status, file_path):
    if upload_status is None:
        raise PreventUpdate
    df = transform_csv(file_path, 31468, 4326)

    if len(df) > 200:
        # Select 200 random points, otherwise the website will freeze for some time
        df = df.sample(n=200, random_state=42)

    points = []
    for index, row in df.iterrows():
        points.append(dl.Marker(position=[row["Latitude"], row["Longitude"]]))

    group = dl.LayerGroup(children=points)

    if len(df) > 200:
        return html.Div(
            [html.H6("Showing 200 random points out of {}".format(len(df))), group]
        )
    else:
        return group


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

    route_creator = RouteCreator(
        "/home/trinkle/git/UFZ-Flask/UFZ-Flask/cosmonaut_app/download/20240424-105506_osm_data_4326.geojson"
    )
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

    route_creator = RouteCreator(
        "/home/trinkle/git/UFZ-Flask/UFZ-Flask/cosmonaut_app/download/20240424-105506_osm_data_4326.geojson"
    )
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