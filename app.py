import os
import dash
from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from werkzeug.utils import secure_filename
import base64
import csv
from transformation import OsmRoads, transform_csv, get_convex_hull
from flask import Flask, send_from_directory
from urllib.parse import quote as urlquote
import time
import json
import pandas as pd
import geopandas as gpd
import shapely.geometry
import numpy as np
import dash_leaflet as dl
from dash_leaflet import express as dlx
from csv_plot import Plotter
import random

UPLOAD_FOLDER = "upload"
DOWNLOAD_FOLDER = "download"
IMAGE_FOLDER = "images"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# Mapbox token
# mb_token = "pk.eyJ1IjoibG91aXN0cmkiLCJhIjoiY2xvbjF4M2h3MDlvZjJ2cXNldThlaG8xdiJ9.mU8urLdPCQo-DyiYhwqtLQ"

external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

server = Flask(__name__)
app = dash.Dash(external_stylesheets=external_stylesheets, server=server)


@server.route("/download/<path:path>")
def download(path):
    """Serve a file from the upload directory."""
    return send_from_directory(UPLOAD_FOLDER, path, as_attachment=True)


@app.server.route("/images/<path:path>")
def serve_image(image_path):
    return send_from_directory(IMAGE_FOLDER, image_path)


# TODO: Remove the geojson layers when the image overlay is working
with open("upload_data/Class3.geojson") as f:
    Class3 = json.load(f)

with open("upload_data/Class4.geojson") as f:
    Class4 = json.load(f)

app.layout = html.Div(
    [
        html.H1("Upload, Transformation, OSM-Request and Display of CSV-data"),
        html.H2("Upload"),
        dcc.Upload(
            id="upload-data",
            accept=".csv",
            children=html.Div(["Drag and drop or click to select a file to upload."]),
            multiple=False,
        ),
        html.H2("File List"),
        html.Ul(id="file-list"),
        html.Div(id="output-data-upload"),
        html.Div(id="output-osm-query"),
        html.Div(id="file-path", style={"display": "none"}),
        html.Div(id="osm-file-path", style={"display": "none"}),
        dl.Map(
            [
                dl.LayersControl(
                    [
                        dl.BaseLayer(
                            dl.TileLayer(), name="OpenStreetMap", checked=True
                        ),
                        dl.Overlay(
                            dl.LayerGroup(), name="points", checked=False, id="points"
                        ),
                        dl.Overlay(
                            dl.LayerGroup(), name="markers", checked=False, id="markers"
                        ),
                        # add the class3 & 4 geojson layers to the layer control
                        dl.Overlay(
                            dl.LayerGroup(
                                dl.GeoJSON(data=Class3, style={"color": "red"})
                            ),
                            name="Class3",
                            checked=True,
                            id="class3",
                        ),
                        dl.Overlay(
                            dl.LayerGroup(dl.GeoJSON(data=Class4)),
                            name="Class4",
                            checked=True,
                            id="class4",
                        ),
                        dl.Overlay(
                            dl.LayerGroup(
                                dl.ImageOverlay(
                                    url="/assets/test.png",
                                    bounds=[
                                        [51.58503255, 10.89955432],
                                        [51.88928492, 11.51882844],
                                    ],
                                    opacity=0.75,
                                    id="image-overlay",
                                )
                            ),
                            name="image-overlay",
                            checked=True,
                        ),
                    ],
                    id="lc",
                ),
                dl.FullScreenControl(),
                dl.LocateControl(locateOptions={"enableHighAccuracy": True}),
                dl.ScaleControl(position="bottomleft"),
            ],
            center=[51.80, 11.32],
            zoom=10,
            style={"height": "50vh"},
            id="map",
        ),
        html.Button(
            "Load new Map", id="btn"
        ),  # not used for now but might be useful later
        html.Div(
            [
                html.H4("OSM Tags Selection"),
                dcc.Dropdown(
                    id="tags-dropdown",
                    options=[
                        {"label": tag, "value": tag}
                        for tag in [
                            "primary",
                            "secondary",
                            "tertiary",
                            "unclassified",
                            "residential",
                            "primary_link",
                            "secondary_link",
                            "tertiary_link",
                            "living_street",
                            "track",
                            "road",
                        ]
                    ],
                    value=[
                        "primary",
                        "secondary",
                        "tertiary",
                        "unclassified",
                        "residential",
                        "primary_link",
                        "secondary_link",
                        "tertiary_link",
                        "living_street",
                        "track",
                        "road",
                    ],
                    multi=True,
                ),
                html.Div(id="tags-points"),
            ]
        ),
    ]
)


def uploaded_files():
    """List the files in the upload directory."""
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(path):
            files.append(filename)
    return files


def file_download_link(filename):
    """Create a Plotly Dash 'A' element that downloads a file from the app."""
    location = "/download/{}".format(urlquote(filename))
    return html.A(filename, href=location)


@app.callback(
    Output("file-list", "children"),
    [Input("upload-data", "filename"), Input("upload-data", "contents")],
)
def update_output(uploaded_filenames, uploaded_file_contents):
    """Save uploaded files and regenerate the file list."""
    time.sleep(1)
    files = uploaded_files()
    if len(files) == 0:
        return [html.Li("No files yet!")]
    else:
        return [html.Li(file_download_link(filename)) for filename in files]


@app.callback(
    Output("output-data-upload", "children"),
    Output("file-path", "children"),
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
)
def upload_file(contents, filename):
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
                return html.Div([html.H5("CSV must have 8 columns")]), None

    return html.Div([html.H5("File uploaded successfully")]), file_path


@app.callback(
    Output("output-osm-query", "children"),
    Output("osm-file-path", "children"),
    Input("output-data-upload", "children"),
    Input("tags-dropdown", "value"),
    State("file-path", "children"),
)
def run_osm_query(upload_status, selected_tags, file_path):
    if upload_status is None:
        raise PreventUpdate
    try:
        data = transform_csv(file_path, 31468, 4326)
        convex_hull = get_convex_hull(data)
        osm = OsmRoads(convex_hull)
        osm._get_roads(additional_tags={"highway": selected_tags})
        osm_file_path = osm.save_roads(DOWNLOAD_FOLDER, 4326)
        osm_file_path
        return html.Div([html.H5("OSM query run successfully")]), osm_file_path
    except Exception as e:
        os.remove(file_path)
        return html.Div([html.H5("OSM query failed")]), None


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
    Output("image-overlay", "url"),
    Output("image-overlay", "bounds"),
    Input("btn", "n_clicks"),
    State("output-data-upload", "children"),
    State("file-path", "children"),
)
def update_image(n_clicks, upload_status, file_path):
    if n_clicks is None:
        raise PreventUpdate

    if upload_status is None:
        raise PreventUpdate

    plotter = Plotter(file_path, 31468, 4326)
    plotter.assign_classes()
    image_base64 = plotter.plot_data()
    image_url = "data:image/png;base64,{}".format(image_base64)
    bounds = plotter.gdf.total_bounds
    bounds = [
        [bounds[1], bounds[0]],
        [bounds[3], bounds[2]],
    ]  # Format: [[south, west], [north, east]]

    return image_url, bounds


# not used for now but might be useful later
# @app.callback(Output("markers", "children"), Input("btn", "n_clicks"))
# def generate_markers(_):
#     return [dl.Marker(position=[51 + random.random(), 11 + random.random()]) for i in range(5)]


if __name__ == "__main__":
    app.run_server(debug=True)
