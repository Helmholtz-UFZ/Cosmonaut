import logging
import logging.config

import dash_bootstrap_components as dbc
from dash import Dash

from cosmonaut_app.config import DEBUG, FLASK_PORT
from cosmonaut_app.error_handling import handle_error
from cosmonaut_app.files_route import serve_files
from cosmonaut_app.layout import (
    app_layout,
    register_navbar_callbacks,
    register_reset_callbacks,
)
from cosmonaut_app.logger import get_logger_config
from cosmonaut_app.object_storage_manager import create_bucket, setup_remote

# Configure application-wide logging
logging.config.dictConfig(get_logger_config(DEBUG))
logger = logging.getLogger(__name__)
logger.info("COSMONAUT application starting")

# --- Flask + Dash setup ---
app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    prevent_initial_callbacks="initial_duplicate",
    assets_url_path="/assets",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="COSMONAUT",
    on_error=handle_error,
)

app.layout = app_layout()

# Serve files
serve_files(app)
# Setup object storage
setup_remote()
create_bucket()

register_navbar_callbacks(app)
register_reset_callbacks(app)

server = app.server  # Expose Flask server for WSGI

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=DEBUG, port=FLASK_PORT)
