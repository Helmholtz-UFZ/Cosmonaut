"""Map and tile layer utilities."""

import logging
import os
import urllib.parse

import dash_leaflet as dl

from cosmonaut_app.config import TILESERVER_URL
from cosmonaut_app.constants.general import MEMBERSHIP_TIF


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
    logging.info(f"Using map URL: {tile_url}")

    return dl.TileLayer(
        url=tile_url, opacity=opacity, crossOrigin="anonymous", bounds=bounds
    )


def get_tile_url(job_id, working_dir):
    """Return TileServer URL for the job's membership GeoTIFF, or '' if absent."""
    tif_path = os.path.join(working_dir, MEMBERSHIP_TIF)
    if not os.path.exists(tif_path):
        return ""
    return create_tile_layer_component(job_id, MEMBERSHIP_TIF, colormap_params="").url
