from flask import Flask, send_from_directory, redirect
from werkzeug.utils import secure_filename
import os
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from cosmonaut_app.layout import side_bar, main_map, navbar

server = Flask(__name__)
app = dash.Dash(
    server=server,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css",
    ],
)

# Suppress callback exceptions because several callbacks need components which are created later
app.config.suppress_callback_exceptions = True

# Generate the layout of the app
app.layout = html.Div(
    [
        navbar,
        side_bar,
        main_map,
        html.Div(id="hidden-div", style={"display": "none"}),
        dcc.Store(id="current-stage", data=0),
        dcc.Store(id="job-status-store", data=None),
    ],
    style={"height": "100vh"},
)
