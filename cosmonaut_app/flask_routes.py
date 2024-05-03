from flask import Flask, send_from_directory, redirect
from werkzeug.utils import secure_filename
import os
import dash
from dash import html

# Create upload and download folders if they do not exist
UPLOAD_FOLDER = "upload"
DOWNLOAD_FOLDER = "download"

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
app = dash.Dash(server=server)


@server.route("/download/<path:path>")
def download(path):
    """Serve a file from the upload directory."""
    return send_from_directory(UPLOAD_FOLDER, path, as_attachment=True)
