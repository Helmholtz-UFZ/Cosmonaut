"""Overpass-based OSM road-network downloader (streaming).

Drop-in replacement for ``cosmonaut_app.osm_downloader.OsmDownloader``: same
constructor signature, same ``run_osm_query`` entry point, same three output
files —

  - ``osm_data_download.geojson``    (EPSG:4326)
  - ``osm_data_edited.geojson``      (EPSG:4326, copy)
  - ``osm_data_transformed.geojson`` (EPSG:``epsg_output``) -> read by sensor-routing

— but it streams ways from the source and writes features incrementally, so peak
RAM stays bounded: one way is parsed, transformed, projected and written at a
time, and the full response is never materialized. See the decision record
docs/decisions/20260605-osm-overpass-direct-vs-osmnx.md.
"""

import logging
import os
import shutil

import numpy as np
import pyproj
import shapely
from sensor_routing.constants import OSM_FILENAME
from shapely.geometry import Polygon

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
)
from cosmonaut_app.osm.geojson_writer import StreamingGeoJsonWriter
from cosmonaut_app.osm.source import OverpassSource
from cosmonaut_app.osm.transform import way_to_feature

log = logging.getLogger(__name__)

# Highway tag values to fetch — identical to the old osmnx custom_filter.
HIGHWAY_TYPES = [
    "motorway",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "track",
]


class OsmDownloader:
    """Download and project OpenStreetMap road data for a classification area.

    Args:
        classification_data: DataFrame with Longitude/Latitude columns.
        epsg_output: EPSG code of the target coordinate system (user-configurable
            in the app; the membership/predictor CRS).
        source: OsmSource backend. Defaults to the configured Overpass endpoint.
    """

    def __init__(self, classification_data, epsg_output=25832, source=None):
        self.polygon = self._get_convex_hull(classification_data)
        self.highway_types = HIGHWAY_TYPES
        self.epsg_input = 4326
        self.epsg_output = epsg_output
        self.source = source if source is not None else OverpassSource()

    @staticmethod
    def _get_convex_hull(classification_data):
        """Calculate the convex hull of the given points and return a buffered polygon."""
        lon = classification_data.Longitude
        lat = classification_data.Latitude

        points = np.array([lon, lat]).T
        hull = Polygon(points).convex_hull
        return hull.buffer(0.005, cap_style="square", join_style=2)

    @staticmethod
    def _project_feature(feature, transformer):
        """Reproject a 4326 feature to the output CRS.

        Drops the top-level ``id`` to match the transformed file sensor-routing
        reads (it keys on ``properties.osmid``). pyproj is exactly what geopandas
        uses underneath, so coordinates match the previous geopandas output.
        """
        coordinates = feature["geometry"]["coordinates"]
        eastings, northings = transformer.transform(
            [lon for lon, lat in coordinates],
            [lat for lon, lat in coordinates],
        )
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [float(easting), float(northing)]
                    for easting, northing in zip(eastings, northings)
                ],
            },
            "properties": feature["properties"],
        }

    def run_osm_query(self, download_folder):
        """Stream ways from the source and write the three output files incrementally."""
        shapely.prepare(self.polygon)
        transformer = pyproj.Transformer.from_crs(
            self.epsg_input, self.epsg_output, always_xy=True
        )

        download_path = os.path.join(download_folder, OSM_DATA_DOWNLOAD_FILE)
        transformed_path = os.path.join(download_folder, OSM_FILENAME)

        count = 0
        with (
            StreamingGeoJsonWriter(download_path) as download_writer,
            StreamingGeoJsonWriter(
                transformed_path, crs_epsg=self.epsg_output
            ) as transformed_writer,
        ):
            for way in self.source.stream_ways(self.polygon, self.highway_types):
                feature = way_to_feature(way, self.polygon)
                if feature is None:
                    continue
                download_writer.write(feature)
                transformed_writer.write(self._project_feature(feature, transformer))
                count += 1

        # The editable copy starts identical to the download (EPSG:4326).
        shutil.copy2(download_path, os.path.join(download_folder, OSM_DATA_EDITED_FILE))
        log.info("Streamed %d road features to %s", count, download_folder)
