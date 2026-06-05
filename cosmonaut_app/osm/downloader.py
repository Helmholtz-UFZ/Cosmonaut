"""Overpass-based OSM road-network downloader.

Drop-in replacement for ``cosmonaut_app.osm_downloader.OsmDownloader``: same
constructor signature, same ``run_osm_query`` entry point, same three output
files —

  - ``osm_data_download.geojson``    (EPSG:4326)
  - ``osm_data_edited.geojson``      (EPSG:4326, copy)
  - ``osm_data_transformed.geojson`` (EPSG:``epsg_output``) -> read by sensor-routing

— but it fetches ways directly from Overpass instead of building (and then
immediately un-building) an osmnx graph. RAM scales with the size of the road
data, not with an in-memory networkx graph over the whole hull.
"""

import json
import logging
import os
import shutil

import geopandas as gpd
import numpy as np
from sensor_routing.constants import OSM_FILENAME
from shapely.geometry import Polygon

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
)
from cosmonaut_app.osm.source import OverpassSource
from cosmonaut_app.osm.transform import ways_to_features

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


def project_and_save(features, dst_path, src_epsg, dst_epsg):
    """Project GeoJSON features to the target CRS and save with a CRS header."""
    gdf = gpd.GeoDataFrame.from_features(features, crs=f"EPSG:{src_epsg}")
    gdf = gdf.to_crs(epsg=dst_epsg)
    gdf.to_file(dst_path, driver="GeoJSON")


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

    def _get_roads(self, download_folder):
        """Fetch ways, build features, and write the two 4326 files.

        Returns:
            list: GeoJSON features in EPSG:4326.
        """
        ways = self.source.fetch_ways(self.polygon, self.highway_types)
        features = ways_to_features(ways, self.polygon)

        feature_collection = {"type": "FeatureCollection", "features": features}

        download_path = os.path.join(download_folder, OSM_DATA_DOWNLOAD_FILE)
        with open(download_path, "w", encoding="utf-8") as f:
            json.dump(feature_collection, f, ensure_ascii=False)

        edit_path = os.path.join(download_folder, OSM_DATA_EDITED_FILE)
        shutil.copy2(download_path, edit_path)

        return features

    def _osm_transform(self, features, download_folder):
        """Project features to the output CRS and save as the transformed file."""
        log.info("Transforming road data to EPSG:%s ...", self.epsg_output)
        project_and_save(
            features,
            os.path.join(download_folder, OSM_FILENAME),
            self.epsg_input,
            self.epsg_output,
        )

    def run_osm_query(self, download_folder):
        features = self._get_roads(download_folder)
        self._osm_transform(features, download_folder)
