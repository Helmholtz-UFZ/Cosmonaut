"""Map and tile layer utilities."""

import logging
import urllib.parse

import dash_leaflet as dl

from cosmonaut_app.config import TILESERVER_URL


def create_tile_layer_component(job_id, tiff_filename, colormap_params, opacity=0.9):
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

    return dl.TileLayer(url=tile_url, opacity=opacity)
