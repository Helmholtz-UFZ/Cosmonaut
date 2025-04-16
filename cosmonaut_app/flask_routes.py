import dash
from dash import dcc, html
from flask import Flask

server = Flask(__name__, static_url_path="/met/wg7/cosmonaut/static")
app = dash.Dash(
    server=server,
    assets_url_path="/assets",
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
        ]
    )


app.layout = serve_layout
