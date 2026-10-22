"""Map and tile layer utilities."""

import logging
import os
import urllib.parse

import dash_leaflet as dl
from cosmo_ecosystem import job_persistence
from sensor_routing.constants import ROUTE_FILENAME

from cosmonaut_app.config import TILESERVER_URL
from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    MEMBERSHIP_TIF,
    ROUTE_OPTIONS_FILE,
)

log = logging.getLogger(__name__)


def create_tile_layer_component(
    job_id, tiff_filename, colormap_params, opacity=0.9, bounds=None
):
    """Create TileLayer component for GeoTIFF using TiTiler.

    This function can be mocked in tests to avoid tile server dependency.
    """
    file_path = f"file:///data/{job_id}/{tiff_filename}"
    encoded_url = urllib.parse.quote(file_path, safe=":/")

    tile_url = (
        f"{TILESERVER_URL}/cog/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}@1x"
        f"?url={encoded_url}&maxzoom=15{colormap_params}"
    )
    log.info(f"Using map URL: {tile_url}")

    return dl.TileLayer(
        url=tile_url, opacity=opacity, crossOrigin="anonymous", bounds=bounds
    )


def get_tile_url(job_id, working_dir):
    """Return TileServer URL for the job's membership GeoTIFF, or '' if absent."""
    tif_path = os.path.join(working_dir, MEMBERSHIP_TIF)
    if not os.path.exists(tif_path):
        return ""
    return create_tile_layer_component(job_id, MEMBERSHIP_TIF, colormap_params="").url


def map_layer_data(job) -> tuple[str, list]:
    """Return the job's membership tile URL and route positions for the map.

    Called on every navigation (the URL changes), not on map moves, on any
    pod: it reads the stored copies through ``job_persistence.pull_file`` (two
    rclone subprocesses per file). The row decides what may be shown, so files
    another pod deleted (reset, deleted membership) but this pod's disk still
    holds never reappear: the raster only once a membership is uploaded, the
    route and its direction only for a completed job.

    Args:
        job: A ``CosmonautJob``.

    Returns:
        ``(tile_url, positions)``: ``""`` without a raster, ``[]`` without a
        route; positions as ``get_route_polyline`` gives them.
    """
    tile_url = ""
    if job.model.membership_upload["file_name"] != "No file uploaded":
        job_persistence.pull_file(job.job_id, MEMBERSHIP_TIF)
        tile_url = get_tile_url(job.job_id, job.working_dir)
    positions = []
    if job.model.status == JOB_STATUS_COMPLETED:
        job_persistence.pull_file(job.job_id, ROUTE_FILENAME)
        job_persistence.pull_file(job.job_id, ROUTE_OPTIONS_FILE)
        positions = job.get_route_polyline() or []
    return tile_url, positions
