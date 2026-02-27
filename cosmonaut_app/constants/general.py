"""General application constants for COSMONAUT."""

LOG_FILE_NAME = "worker.log"
GPX_FILE = "route.gpx"
QR_CODE_FILE = "qr_code.png"

# Membership raster (WGS84 GeoTIFF for TiTiler)
MEMBERSHIP_TIF = "membership.tif"

# Job status constants
JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_FAILED = "FAILED"

# Maintenance constants
LOG_RETENTION_DAYS = 30  # Days to retain logs in PostgreSQL database

# OSM data file names
OSM_DATA_DOWNLOAD_FILE = "osm_data_download.geojson"
OSM_DATA_EDITED_FILE = "osm_data_edited.geojson"

# Mapping of road classification labels to OSM highway tag values
OSM_TAGS_MAPPING = {
    "Motorway": ["motorway", "motorway_link"],
    "Trunk road": ["trunk", "trunk_link"],
    "Primary road": ["primary", "primary_link"],
    "Secondary road": ["secondary", "secondary_link"],
    "Tertiary road": ["tertiary", "tertiary_link"],
    "Unclassified": ["unclassified"],
    "Residential": ["residential"],
    "Living street": ["living_street"],
    "Track": ["track"],
}

# Default map view (Germany)
DEFAULT_MAP_CENTER = [51.70, 11.20]
DEFAULT_MAP_ZOOM = 10
