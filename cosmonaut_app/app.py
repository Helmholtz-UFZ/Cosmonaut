import os
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from werkzeug.utils import secure_filename
import base64
import csv
from transformation import OsmRoads, transform_csv, get_convex_hull
from flask import Flask, send_from_directory
import time
import dash_leaflet as dl
from matplotlib import pyplot as plt
from classification_plot import ClassificationPlot
from minio_manager import MiniIOManager
from config import osm_tags_mapping
import matplotlib

matplotlib.use("Agg")

UPLOAD_FOLDER = "upload"
DOWNLOAD_FOLDER = "download"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

server = Flask(__name__)
app = dash.Dash(
    server=server
)  # external_stylesheets=external_stylesheets, server=server)


@server.route("/download/<path:path>")
def download(path):
    """Serve a file from the upload directory."""
    return send_from_directory(UPLOAD_FOLDER, path, as_attachment=True)


app.layout = html.Div(
    [
        html.Div(
            [
                html.H1(
                    "COSmic ray based soil MOisture prediction NAvigation Utility Tool"
                )  # ,
                # html.H3("or short"),
                # html.H2("COSMONAUT"),
            ],
            style={"text-align": "center", "padding-bottom": "20px"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H2("Upload"),
                        dcc.Upload(
                            id="upload-data",
                            accept=".csv",
                            children=html.Div(
                                ["Drag and drop or click to select a file to upload."]
                            ),
                            multiple=False,
                        ),
                        html.H2("File List"),
                        html.Ul(id="file-list"),
                        html.Div(id="output-data-upload"),
                        html.Div(id="output-osm-query"),
                        html.Div(id="file-path", style={"display": "none"}),
                        html.Div(id="osm-file-path", style={"display": "none"}),
                    ],
                    style={"flex": "1 1 20%", "padding-right": "20px"},
                ),
                html.Div(
                    [
                        dl.Map(
                            [
                                dl.LayersControl(
                                    [
                                        dl.BaseLayer(
                                            dl.TileLayer(),
                                            name="OpenStreetMap",
                                            checked=True,
                                        ),
                                        dl.Overlay(
                                            dl.LayerGroup(),
                                            name="points",
                                            checked=False,
                                            id="points",
                                        ),
                                    ],
                                    id="lc",
                                ),
                                dl.FullScreenControl(),
                                dl.LocateControl(
                                    locateOptions={"enableHighAccuracy": True}
                                ),
                                dl.ScaleControl(position="bottomleft"),
                            ],
                            center=[51.70, 11.20],
                            zoom=10,
                            style={"height": "50vh", "border": "2px solid black"},
                            id="map",
                        ),
                        html.Button(
                            "Load new Map", id="btn", style={"margin-top": "10px"}
                        ),
                    ],
                    style={"flex": "1 1 80%", "margin-top": "10px"},
                ),
            ],
            style={"display": "flex", "justify-content": "center"},
        ),
        html.Div(
            [
                html.H4("OSM Highway tag selection"),
                dcc.Dropdown(
                    id="tags-dropdown",
                    options=[{"label": tag, "value": tag} for tag in osm_tags_mapping.keys()],
                    value=list(osm_tags_mapping.keys()),
                    multi=True,
                    style={"width": "50%", "margin": "0 auto"},
                ),
            ],
            style={"text-align": "center", "padding-top": "20px"},
        ),
        html.Div(id="plot-generation-status", style={"display": "none"}),
    ],
    style={"padding": "20px"},
)


def uploaded_files():
    """List the files in the upload directory."""
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(path):
            files.append(filename)
    return files


def file_link(filename):
    """Create a Plotly Dash 'A' element that just shows the fils uploaded."""
    return html.A(filename, href="#", id=filename)


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
        return [html.Li(file_link(filename)) for filename in files]


@app.callback(
    Output("upload-data", "contents"),
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
    Output("output-osm-query", "children"),
    Output("osm-file-path", "children"),
    [Input("output-data-upload", "children")],
    [State("file-path", "children"), State("tags-dropdown", "value")],
)
def run_osm_query(upload_status, file_path, selected_tags):
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
        osm._get_roads(additional_tags=additional_tags)

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
        return (
            html.Div(
                [html.H5("OSM query failed"), html.P(str(e))],
                className="fade-out",
                key=str(time.time()),
            ),
            None,
        )


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
        return html.Div(
            [html.H5("Plot generation failed"), html.P(str(e))],
            className="fade-out",
            key=str(time.time()),
        )


if __name__ == "__main__":
    app.run_server(debug=True)
