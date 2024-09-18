import time
import pandas as pd
import numpy as np
import time
from shapely.geometry import Polygon
from pyproj import CRS, Transformer
import osmnx as ox
import time
import os
import geojson
from pyproj import CRS, Transformer


def transform_csv(input_file, epsg_input, epsg_output):
    """
    Transforms the coordinates in a CSV file from one coordinate reference system (CRS) to another.

    Args:
        input_file (str): Path to the input CSV file.
        epsg_input (int): EPSG code of the input CRS.
        epsg_output (int): EPSG code of the output CRS.

    Returns:
        pandas.DataFrame: DataFrame with transformed coordinates.
    """
    if not input_file.endswith(".csv"):
        raise ValueError("Input file must be a CSV file.")

    crs_output = CRS.from_epsg(epsg_output)
    crs_input = CRS.from_epsg(epsg_input)
    transformer = Transformer.from_crs(crs_input, crs_output)

    df = pd.read_csv(input_file)

    df["Latitude"], df["Longitude"] = transformer.transform(
        df["Easting (m)"].values, df["Northing (m)"].values
    )

    df.drop(["Easting (m)", "Northing (m)"], axis=1, inplace=True)

    return df


def get_convex_hull(self):
    """
    Calculate the convex hull of the given points and return a buffered polygon.

    Returns:
        A buffered polygon representing the convex hull of the points.
    """
    lon = self.Longitude
    lat = self.Latitude

    points = np.array([lon, lat]).T
    points = Polygon(points)
    hull = points.convex_hull
    hull_buffer = hull.buffer(0.005, cap_style="square", join_style=2)

    return hull_buffer


def _get_bounds(self):
    """
    Calculate the rectangular bounds of the given points.

    Returns:
        A list containing the minimum latitude, minimum longitude,
        maximum latitude, and maximum longitude.
    """
    lon = self.Longitude
    lat = self.Latitude

    min_lon, max_lon = lon.min(), lon.max()
    min_lat, max_lat = lat.min(), lat.max()

    return [[min_lat, min_lon], [max_lat, max_lon]]


class OsmRoads:
    """
    A class for handling OpenStreetMap road data transformation.

    Args:
        polygon (shapely.geometry.Polygon): The polygon representing the area of interest.
        epsg_input (int, optional): The EPSG code of the input coordinate system. Defaults to 4326.
        epsg_output (int, optional): The EPSG code of the output coordinate system. Defaults to 31468.
    """

    def __init__(self, polygon, epsg_input=4326, epsg_output=31468):
        self.polygon = polygon
        self.tags = {
            "highway": [
                "motorway",
                "trunk",
                "primary",
                "secondary",
                "tertiary",
                "motorway_link",
                "trunk_link",
                "primary_link",
                "secondary_link",
                "tertiary_link",
                "unclassified",
                "residential",
                "living_street",
                "track",
            ]
        }
        self.epsg_input = epsg_input
        self.epsg_output = epsg_output

    def _get_roads(self, additional_tags: dict = None):
        """
        Get road data from OpenStreetMap based on the specified tags.

        Args:
            additional_tags (dict, optional): Additional tags to filter the road data. Defaults to None.

        Returns:
            geopandas.GeoDataFrame: The road data as a GeoDataFrame.
        """
        if additional_tags is not None:
            self.tags = additional_tags
        osm_data = ox.features_from_polygon(self.polygon, tags=self.tags)
        columns_to_keep = [
            "geometry",
            "name",
            "highway",
            "nodes",
            "bicycle",
            "smoothness",
            "surface",
            "tracktype",
            "maxspeed",
            "sidewalk",
            "lanes",
            "lit",
            "motor_vehicle",
            "ref",
            "source:maxspeed",
            "lanes:backward",
            "traffic_calming",
            "oneway",
        ]
        columns_to_keep = [col for col in columns_to_keep if col in osm_data.columns]
        osm_data = osm_data[columns_to_keep]
        return osm_data

    def save_roads(self, DOWNLOAD_FOLDER, epsg_code, additional_tags: dict = None):
        self.roads = self._get_roads(additional_tags)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        file_name = f"{timestamp}_osm_data_{epsg_code}.geojson"
        file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
        with open(
            file_path, "w"
        ) as osm_file:  # TODO Is it necessary to write the file here?
            geojson.dump(self.roads, osm_file)
        return file_path

    def _osm_transform(self):
        osm_data = self.roads
        epsg_output = self.epsg_output
        epsg_input = self.epsg_input
        osm_data = osm_data.to_crs(epsg=epsg_output)
        return osm_data
