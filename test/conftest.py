"""Setup tests."""

import logging

import pytest
from sqlalchemy.exc import OperationalError

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
