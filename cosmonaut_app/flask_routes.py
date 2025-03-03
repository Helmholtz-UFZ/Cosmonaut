import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from flask import Flask

server = Flask(__name__)
app = dash.Dash(
    server=server,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "'src': 'hfont-awesome.min.css'",
        "'src': '/assets/resize.js'",
    ],
    requests_pathname_prefix="/met/wg7/cosmonaut/",
    routes_pathname_prefix="/met/wg7/cosmonaut/",
)

# Suppress callback exceptions because
# several callbacks need components which are created later
app.config.suppress_callback_exceptions = True


def serve_layout():
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            html.Div(id="page-content"),
            dcc.Store(id="job-id", data=None),
            dcc.Store(id="job-page-loaded", data=False),
            dcc.Store(id="amount-classes-input", data=0),
        ]
    )


app.layout = serve_layout
