import logging
import logging.config
from pathlib import Path

from cosmo_suite.logger import get_logger_config_web
from cosmo_suite.object_storage_manager import create_bucket, setup_remote
from dash import Dash

from cosmonaut_app.config import DEBUG, PORT
from cosmonaut_app.constants.general import EXCLUDED_LOG_PACKAGES
from cosmonaut_app.error_handling import handle_error_with_notification
from cosmonaut_app.files_route import serve_files
from cosmonaut_app.layout import (
    app_layout,
    register_map_callbacks,
    register_navbar_callbacks,
    register_reset_callbacks,
)

# Configure application-wide logging
logging.config.dictConfig(get_logger_config_web(DEBUG, EXCLUDED_LOG_PACKAGES))
logger = logging.getLogger(__name__)
logger.info("COSMONAUT application starting")

# --- Flask + Dash setup ---
app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    prevent_initial_callbacks=True,
    assets_url_path="/assets",
    title="COSMONAUT",
    on_error=handle_error_with_notification,
)

app.layout = app_layout()

# Serve files
serve_files(app)
# Setup object storage
setup_remote()
create_bucket()

register_navbar_callbacks(app)
register_reset_callbacks(app)
register_map_callbacks(app)

server = app.server  # Expose Flask server for WSGI

# No Celery Beat here: it runs embedded in the worker (docker/worker.Dockerfile).
# Gunicorn with --preload imports this module once and then forks its workers; a
# thread started at import can hold one of Celery's internal locks at that moment,
# and the forked worker then blocks forever on its first task submission. Without
# --preload every worker would start its own Beat instead, and every scheduled task
# would run once per worker. See docs/conventions/celery_beat.md in cosmo-suite.

if __name__ == "__main__":
    # Watch local sensor-routing source for auto-reload (mounted via --local-sr)
    local_sr = Path("/python_docker/sensor-routing/sensor_routing")
    extra = list(local_sr.rglob("*.py")) if local_sr.is_dir() else []
    app.run(host="0.0.0.0", debug=DEBUG, port=PORT, extra_files=extra)
