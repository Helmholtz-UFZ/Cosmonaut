import os

from dash import Dash
import dash_bootstrap_components as dbc

from cosmonaut_app.error_handling import handle_error
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.layout import (
    app_layout,
    register_navbar_callbacks,
    register_shared_store_callbacks,
    register_map_callbacks,
)

# --- Flask + Dash setup ---
app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    assets_url_path="/assets",
    external_stylesheets=[dbc.themes.FLATLY],
    title="COSMONAUT",
    on_error=handle_error,
)

app.layout = app_layout()

register_navbar_callbacks(app)
register_shared_store_callbacks(app)
register_map_callbacks(app)

if __name__ == "__main__":
    # Read DEBUG from environment variable (default to False)
    debug_mode = os.getenv("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", debug=debug_mode, port=FLASK_PORT)
