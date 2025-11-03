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
from cosmonaut_app.error_handling import handle_error, error_modal
from cosmonaut_app.constants.html_ids import (
    CURRENT_STAGE_STORE_SHARED_ID,
    EMAIL_STORE_SHARED_ID,
    EPSG_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    JOB_LOADED_FLAG_STORE_SHARED_ID,
    URL_DIV_NAV_SHARED_ID,
)
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
    on_error=handle_error,
)

logging.info(
    "Registered pages: %s", {k: v.get("path") for k, v in page_registry.items()}
)


# --- Layout setup ---
def serve_layout():
    return dbc.Container(
        [
            dcc.Location(id=URL_DIV_NAV_SHARED_ID, refresh="callback-nav"),
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
            dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=None),
            dcc.Store(id=CURRENT_STAGE_STORE_SHARED_ID, data=0),
            dcc.Store(id=JOB_LOADED_FLAG_STORE_SHARED_ID, data=None),
            dcc.Store(id=EMAIL_STORE_SHARED_ID),
            dcc.Store(id=EPSG_STORE_SHARED_ID, data=None),
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
            error_modal,
        ],
        fluid=True,
        style={"padding": 0},
    )


app.layout = serve_layout
