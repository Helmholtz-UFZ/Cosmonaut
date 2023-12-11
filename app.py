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

with open("upload_data/Class3.geojson") as f:
    Class3 = json.load(f)

with open("upload_data/Class4.geojson") as f:
    Class4 = json.load(f)

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
            [dl.BaseLayer(dl.TileLayer(), name="OpenStreetMap", checked=True),
            dl.Overlay(dl.LayerGroup(), name="points", checked=False, id='points'),
            dl.Overlay(dl.LayerGroup(), name="markers", checked=False, id='markers'),
            # add the class3 & 4 geojson layers to the layer control
            dl.Overlay(dl.LayerGroup(dl.GeoJSON(data=Class3, style={'color': 'red'})), name="Class3", checked=True, id='class3'),
            dl.Overlay(dl.LayerGroup(dl.GeoJSON(data=Class4)), name="Class4", checked=True, id='class4'),
            ], id="lc"
        ),
        dl.FullScreenControl(),
        dl.LocateControl(locateOptions={'enableHighAccuracy': True}),
        dl.ScaleControl(position="bottomleft"),
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

@app.callback(Output('output-osm-query', 'children'),
              Output('osm-file-path', 'children'),
              Input('output-data-upload', 'children'),
              State('file-path', 'children'))
def run_osm_query(upload_status, file_path):
    if upload_status is None:
        raise PreventUpdate
    try:
        with open(file_path, 'r') as file:
            data = transform_csv(file_path, 31468, 4326)
            convex_hull = get_convex_hull(data)
            osm = OsmRoads(convex_hull)
            osm_data = osm._get_roads()
        osm_file_path = osm.save_roads(DOWNLOAD_FOLDER, 4326)
        osm_file_path
        return html.Div([
            html.H5('OSM query run successfully')
        ]), osm_file_path
    except Exception as e:
        os.remove(file_path)
        return html.Div([
            html.H5('OSM query failed')
        ]), None

@app.callback(Output('points', 'children'),
              Input('output-data-upload', 'children'),
              State('file-path', 'children'))
def show_points(upload_status, file_path):
    if upload_status is None:
        raise PreventUpdate
    df = transform_csv(file_path, 31468, 4326)
    
    if len(df) > 200:
        df = df.sample(n=200, random_state=42)  # Select 200 random points
    
    points = []
    for index, row in df.iterrows():
        points.append(dl.Marker(position=[row['Latitude'], row['Longitude']]))
    
    group = dl.LayerGroup(children=points)
    
    if len(df) > 200:
        return html.Div([
            html.H6('Showing 200 random points out of {}'.format(len(df))),
            group
        ])
    else:
        return group
    
# TODO Make a display of the classes in the csv with polygons for each class where it is the highest compared to the other classes

@app.callback(Output('classes', 'children'),
              Input('output-data-upload', 'children'),
              State('file-path', 'children'))
def show_classes(upload_status, file_path):
    if upload_status is None:
        raise PreventUpdate

    df = transform_csv(file_path, 31468, 4326)

    class_columns = [col for col in df.columns if col.startswith('Class')]
    df['highest_class'] = df[class_columns].apply(lambda row: row.idxmax() if row.max() > 0 else 'NoClass', axis=1)
    df.drop(class_columns, axis=1, inplace=True)

    geometry = [
        shapely.geometry.Point(row['Longitude'], row['Latitude'])
        if not pd.isna(row['Latitude']) and not pd.isna(row['Longitude'])
        else None
        for _, row in df.iterrows()
    ]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
    gdf.drop(['Latitude', 'Longitude'], axis=1, inplace=True)
    gdf = gdf.dissolve(by='highest_class', aggfunc='sum')
    gdf.reset_index(inplace=True)

    classes = []
    for index, row in gdf.iterrows():
        classes.append(dl.GeoJSON(data=json.dumps(row.geometry.__geo_interface__)))

    return classes

# not used for now
# @app.callback(Output("markers", "children"), Input("btn", "n_clicks"))
# def generate_markers(_):
#     return [dl.Marker(position=[51 + random.random(), 11 + random.random()]) for i in range(5)]


if __name__ == '__main__':
    app.run_server(debug=True)
