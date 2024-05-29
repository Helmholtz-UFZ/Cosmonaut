from flask import Flask, send_from_directory, redirect
from werkzeug.utils import secure_filename
import os
import dash
from dash import html
import dash_bootstrap_components as dbc
from cosmonaut_app.layout import side_bar, main_map

# Create upload and download folders if they do not exist
UPLOAD_FOLDER = "cosmonaut_app/upload"
DOWNLOAD_FOLDER = "cosmonaut_app/download"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)


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


server = Flask(__name__)
app = dash.Dash(server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Generate the layout of the app
app.layout = html.Div(
    [
        # html.H1(
        #     "COSmic ray based soil MOisture prediction NAvigation Utility Tool"
        # ),
        side_bar,
        main_map,
        html.Div(id="hidden-div", style={"display": "none"}),
    ],
    style={"height": "100vh"},
)


@server.route("/download/<path:path>")
def download(path):
    """Serve a file from the upload directory."""
    return send_from_directory(UPLOAD_FOLDER, path, as_attachment=True)
