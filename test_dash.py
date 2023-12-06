import os
import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from werkzeug.utils import secure_filename
import base64
import csv
import geojson
from transformation import process_csv_file, transfrom_csv
from flask import Flask, send_from_directory
from urllib.parse import quote as urlquote
import time
import json
import geopandas as gpd
import shapely.geometry
import numpy as np
import dash_leaflet as dl
import random


UPLOAD_FOLDER = "upload"
DOWNLOAD_FOLDER = "download"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Mapbox token
# mb_token = "pk.eyJ1IjoibG91aXN0cmkiLCJhIjoiY2xvbjF4M2h3MDlvZjJ2cXNldThlaG8xdiJ9.mU8urLdPCQo-DyiYhwqtLQ"

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = Flask(__name__)
app = dash.Dash(external_stylesheets=external_stylesheets, server=server)

@server.route("/download/<path:path>")
def download(path):
    """Serve a file from the upload directory."""
    return send_from_directory(UPLOAD_FOLDER, path, as_attachment=True)

app.layout = html.Div([
    html.H1("Upload, Transformation, OSM-Request and Display of CSV-data"),
    html.H2("Upload"),
    dcc.Upload(
        id='upload-data',
        accept=".csv",
        children=html.Div(
            ["Drag and drop or click to select a file to upload."]
        ),
        multiple=False
    ),
    html.H2("File List"),
    html.Ul(id="file-list"),
    html.Div(id='output-data-upload'),
    html.Div(id='output-osm-query'),
    html.Div(id='file-path', style={'display': 'none'}),
    html.Div(id='osm-file-path', style={'display': 'none'}),
    dl.Map([
        dl.LayersControl(
            [dl.BaseLayer(dl.TileLayer(),
                          name="OpenStreetMap", checked=True),
             dl.Overlay(dl.LayerGroup(), name="points", checked=True, id='points'),
             dl.Overlay(dl.LayerGroup(), name="markers", checked=True, id='markers')]
        ),
        dl.FullScreenControl(),
        dl.LocateControl(locateOptions={'enableHighAccuracy': True}),
        dl.ScaleControl(position="bottomleft")
        ], center=[52.5, 13.4], zoom=8, style={'height': '50vh'}, id='map'),
        html.Button("Generate markers", id="btn")
])

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

# Upload the file and check if it is a csv file and has 8 columns
@app.callback(Output('output-data-upload', 'children'),
              Output('file-path', 'children'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'))
def upload_file(contents, filename):
    if contents is None:
        raise PreventUpdate

    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    filename = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    with open(file_path, 'wb') as f:
        f.write(decoded)

    with open(file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            if len(row) != 8:
                os.remove(file_path)
                return html.Div([
                    html.H5('CSV must have 8 columns')
                ]), None

    return html.Div([
        html.H5('File uploaded successfully')
    ]), file_path

# run the transformation on the uploaded csv file and query the osm api
@app.callback(Output('output-osm-query', 'children'),
              Output('osm-file-path', 'children'),
              Input('output-data-upload', 'children'),
              State('file-path', 'children'))
def run_osm_query(upload_status, file_path):
    if upload_status is None:
        raise PreventUpdate
    try:
        with open(file_path, 'r') as file:
            osm_data = process_csv_file(file)
        osm_file_path = os.path.join(DOWNLOAD_FOLDER, "osm_data.geojson")
        with open(osm_file_path, "w") as osm_file:
            geojson.dump(osm_data, osm_file)
        return html.Div([
            html.H5('OSM query run successfully')
        ]), osm_file_path
    except Exception as e:
        os.remove(file_path)
        return html.Div([
            html.H5('OSM query failed')
        ]), None

# now lets add the points out of the csv file which is uploaded into the file list.
# the points are as Easting (m),Northing (m) in the csv file.
# they are in epsg 31468 and need to be converted to 4326 first for the map.
# add the points to the map as a layer and add a marker to each point. but group them in a layer group.
# add a layer control to the map to switch the points on and off.
# TODO make it work for bigger files. choose a random sample of the points and display them or something like that.
@app.callback(Output('points', 'children'),
              Input('output-data-upload', 'children'),
              State('file-path', 'children'))
def show_points(upload_status, file_path):
    if upload_status is None:
        raise PreventUpdate
    df = transfrom_csv(file_path, 31468, 4326)
    points = []
    for index, row in df.iterrows():
        points.append(dl.Marker(position=[row['Latitude'], row['Longitude']]))
    group = dl.LayerGroup(children=points)
    return group

@app.callback(Output("markers", "children"), Input("btn", "n_clicks"))
def generate_markers(_):
    return [dl.Marker(position=[51 + random.random(), 11 + random.random()]) for i in range(5)]


if __name__ == '__main__':
    app.run_server(debug=True)
