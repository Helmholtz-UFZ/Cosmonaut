"""General application constants for COSMONAUT."""

# Constants for file names
SOLUTION_FILE = "solution_transformed.json"
LOG_FILE_NAME = "worker.log"
GPX_FILE = "route.gpx"
QR_CODE_FILE = "qr_code.png"

# Classification plot file templates ({epsg} = e.g. "EPSG:25832")
CLASSIFICATION_PLOT_TEMPLATE = "job_work_dir_{epsg}_output.tif"
CLASSIFICATION_PLOT_4326_TEMPLATE = "job_work_dir_{epsg}_output_4326.tif"

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
