"""General application constants for COSMONAUT."""

LOG_FILE_NAME = "worker.log"
GPX_FILE = "route.gpx"
QR_CODE_FILE = "qr_code.png"
# Per-job presentation options for the computed route (currently: direction).
# File-based like street_edits.json — interactive, reversible, no DB column.
ROUTE_OPTIONS_FILE = "route_options.json"

# Membership raster (WGS84 GeoTIFF for TiTiler)
MEMBERSHIP_TIF = "membership.tif"

# Job status constants
JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_RUNNING = "RUNNING"
JOB_STATUS_COMPLETED = "COMPLETED"
JOB_STATUS_FAILED = "FAILED"

# Maintenance constants
LOG_RETENTION_DAYS = 30  # Days to retain logs in PostgreSQL database

# Third-party packages whose DEBUG output would otherwise fill the logs table.
# Passed to every cosmo_suite.logger builder; the framework adds its own
# (watchdog, selenium) on top, so those are not repeated here. All four run
# inside worker processes, which is where the volume comes from.
EXCLUDED_LOG_PACKAGES = ("matplotlib", "PIL", "pyogrio", "rasterio")

# OSM data file names
OSM_DATA_DOWNLOAD_FILE = "osm_data_download.geojson"
OSM_DATA_EDITED_FILE = "osm_data_edited.geojson"
STREET_EDITS_FILE = "street_edits.json"

# Mapping of road classification labels to OSM highway tag values.
# Must only offer types the download actually fetches (HIGHWAY_TYPES in
# osm/downloader.py) — a filter option without data would be a silent no-op.
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

# OSM ``tracktype`` values for highway=track ways, ordered from solid surface
# (grade1: paved or heavily compacted) to soft surface (grade5: uncompacted).
TRACK_GRADES = ["grade1", "grade2", "grade3", "grade4", "grade5"]
# Bucket for tracks without a standard tracktype tag — common in OSM.
UNGRADED_TRACK_GRADE = "ungraded"
# Default: grades 1-3 only (field practice). Grades 4-5 are rarely
# traversable by survey vehicles; untagged tracks have an unknown condition,
# so they are excluded by default too and can be re-enabled via the
# "No grade tag" option. Applied both at download time (osm/downloader.py)
# and as the initial street-edit state (street_selector.py).
DEFAULT_TRACK_GRADES = ["grade1", "grade2", "grade3"]

# Default map view (Germany)
DEFAULT_MAP_CENTER = [51.70, 11.20]
DEFAULT_MAP_ZOOM = 10
