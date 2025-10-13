# import dash
from dash import (
    dcc,
    html,
    Dash,
    page_container,
    page_registry,
)
import dash_bootstrap_components as dbc
from flask import Flask
from cosmonaut_app.layout import navbar, main_map
import os
import logging

# --- Flask + Dash setup ---
server = Flask(__name__)
app = Dash(
    server=server,
    suppress_callback_exceptions=True,
    assets_url_path="/assets",
    title="COSMONAUT",
    use_pages=True,
    pages_folder=os.path.join(os.path.dirname(__file__), "pages"),  # ensure discovery
)

logging.info(
    "Registered pages: %s", {k: v.get("path") for k, v in page_registry.items()}
)


# --- Layout setup ---
def serve_layout():
    return dbc.Container(
        [
            dcc.Location(id="url", refresh="callback-nav"),
            navbar,
            # 2/3 map + 1/3 sidebar via CSS grid
            html.Div(
                [
                    html.Div(main_map, className="map-panel"),
                    html.Div([page_container], className="sidebar-panel"),
                ],
                className="app-grid",
            ),
            # Hidden divs, Stores, etc.
            html.Div(id="hidden-div", style={"display": "none"}),
            dcc.Store(id="job-id", data=None),
            dcc.Store(id="current-stage", data=0),
            dcc.Store(id="job-loaded-flag", data=None),
            dcc.Store(id="email-store"),
            dcc.Store(id="epsg-store", data=None),
            # Overlay displayed on small screens only (styled via assets CSS)
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("Desktop only"),
                            html.P(
                                "This app is optimized for desktop. Please use a device with a larger screen or widen your browser window."
                            ),
                        ],
                        className="box",
                    )
                ],
                id="unsupported-screen-overlay",
            ),
        ],
        fluid=True,
        style={"padding": 0},
    )


app.layout = serve_layout
