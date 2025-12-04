"""Setup tests."""

import logging
import threading
import time

import pytest
from sqlalchemy.exc import OperationalError

from cosmonaut_app.app import app
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.db_manager import DataBaseManager


def create_logger():
    """Create a logger with debug level."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
    logging.getLogger("PIL").setLevel(logging.CRITICAL)
    logging.getLogger("osgeo").setLevel(logging.ERROR)
    logging.getLogger("rasterio").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("wcs201").setLevel(logging.ERROR)
    return logger


log = create_logger()

try:
    result = DataBaseManager.check_existence("test")
    logging.info(f"Database connection successful. Test query result: {result}")
except OperationalError as e:
    logging.error(f"Database connection failed with OperationalError: {e}")
    pytest.exit(f"postgres not available: {e}")
except Exception as e:
    logging.error(f"Unexpected error during database check: {e}")
    pytest.exit(f"Database check failed: {e}")


@pytest.fixture
def logger():
    """Create a logger with suppressed external sources."""
    return create_logger()


@pytest.fixture(scope="module")
def dash_app():
    """Start the Dash app in a background thread."""

    def run_app():
        app.run(debug=False, port=int(FLASK_PORT))

    thread = threading.Thread(target=run_app, daemon=True)
    thread.start()

    # Give the server time to start
    time.sleep(3)

    yield app

    # Cleanup is automatic since thread is daemon
