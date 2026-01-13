"""Constants package for COSMONAUT application.

This package contains all application constants.
Import constants explicitly from their respective modules:
    from cosmonaut_app.constants.html_ids import SOME_CONSTANT_ID
"""

# Constants for file names
SOLUTION_FILE = "solution_transformed.json"
LOG_FILE_NAME = "worker.log"

# Job status constants
JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_FAILED = "FAILED"

# Maintenance constants
LOG_RETENTION_DAYS = 30  # Days to retain logs in PostgreSQL database

# OSM data file names
OSM_DATA_FILE = "osm_data.geojson"
OSM_DATA_TRANSFORMED_FILE = "osm_data_transformed.geojson"

# Default map view (Germany)
DEFAULT_MAP_CENTER = [51.70, 11.20]
DEFAULT_MAP_ZOOM = 10
