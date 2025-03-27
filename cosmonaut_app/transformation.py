import os

import geojson
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import CRS, Transformer
from shapely.geometry import Polygon


def transform_csv(input_file, epsg_input, epsg_output):
    """
    Transforms the coordinates in a CSV file
    from one coordinate reference system (CRS) to another.

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


# TODO The transformation into a correct geojson format should be in CANs Sensor-routing package
def transform_solution(input_file, epsg_input, epsg_output, reversed_coords=False):
    """
    Transforms the coordinates of sensor-routing solution .json
    from one coordinate reference system (CRS) to another and
    converts the solution to GeoJSON format.
    """
    if not input_file.endswith(".json"):
        raise ValueError("Input file must be a .json file.")
    if not os.path.exists(input_file):
        raise FileNotFoundError("Input file does not exist.")

    with open(input_file, "r") as f:
        data = geojson.load(f)

    crs_output = CRS.from_epsg(epsg_output)
    crs_input = CRS.from_epsg(epsg_input)
    transformer = Transformer.from_crs(crs_input, crs_output)

    # Transform the coordinates in the "Path" key
    if reversed_coords:
        transformed_path = [transformer.transform(y, x) for x, y in data["Path"]]
        transformed_path = [(lon, lat) for lat, lon in transformed_path]
    else:
        transformed_path = [transformer.transform(x, y) for x, y in data["Path"]]

    # Create GeoJSON features
    features = []
    for i in range(len(transformed_path) - 1):
        start = transformed_path[i]
        end = transformed_path[i + 1]
        # Ensure the coordinates are saved as (longitude, latitude)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[start[1], start[0]], [end[1], end[0]]],
                },
                "properties": {},
            }
        )

    geojson_data = {"type": "FeatureCollection", "features": features}

    # Save the transformed data to a new file
    output_file = os.path.join(os.path.dirname(input_file), "solution_transformed.json")
    with open(output_file, "w") as f:
        geojson.dump(geojson_data, f)

    return geojson_data


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


def transform_geojson(input_file, epsg_input, epsg_output):
    """
    Transforms the coordinates in a GeoJSON file
    from one coordinate reference system (CRS) to another.

    Args:
        input_file (str): Path to the input GeoJSON file.
        epsg_input (int): EPSG code of the input CRS.
        epsg_output (int): EPSG code of the output CRS.

    Returns:
        dict: GeoJSON data with transformed coordinates.
    """
    if not input_file.endswith(".geojson"):
        raise ValueError("Input file must be a GeoJSON file.")

    # Initialize CRS and transformer
    crs_input = CRS.from_epsg(epsg_input)
    crs_output = CRS.from_epsg(epsg_output)
    transformer = Transformer.from_crs(crs_input, crs_output, always_xy=True)

    # Load the input GeoJSON file
    with open(input_file, "r") as f:
        data = geojson.load(f)

    # Transform the coordinates in the "geometry" key
    for feature in data["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Point":
            x, y = geometry["coordinates"]
            transformed_x, transformed_y = transformer.transform(x, y)
            geometry["coordinates"] = [transformed_x, transformed_y]
        elif geometry["type"] == "LineString":
            coordinates = geometry["coordinates"]
            transformed_coordinates = [
                transformer.transform(x, y) for x, y in coordinates
            ]
            geometry["coordinates"] = transformed_coordinates
        elif geometry["type"] == "Polygon":
            coordinates = geometry["coordinates"]
            transformed_coordinates = [
                [transformer.transform(x, y) for x, y in ring] for ring in coordinates
            ]
            geometry["coordinates"] = transformed_coordinates
        elif geometry["type"] == "MultiLineString":
            coordinates = geometry["coordinates"]
            transformed_coordinates = [
                [transformer.transform(x, y) for x, y in line] for line in coordinates
            ]
            geometry["coordinates"] = transformed_coordinates
        elif geometry["type"] == "MultiPolygon":
            coordinates = geometry["coordinates"]
            transformed_coordinates = [
                [[transformer.transform(x, y) for x, y in ring] for ring in polygon]
                for polygon in coordinates
            ]
            geometry["coordinates"] = transformed_coordinates
        else:
            raise ValueError(f"Unsupported geometry type: {geometry['type']}")

        if "element_type" not in feature["properties"]:
            feature["properties"]["element_type"] = "way"

    return data


def update_geojson_ids(input_file, output_file):
    """
    Updates the GeoJSON file by moving the 'id' field into 'properties["osmid"]'
    and removing the 'id' field.

    Args:
        input_file (str): Path to the input GeoJSON file.
        output_file (str): Path to save the updated GeoJSON file.
    """
    with open(input_file, "r") as f:
        data = geojson.load(f)

    for feature in data["features"]:
        # Extract the numeric part of the 'id' field and move it to 'properties["osmid"]'
        if isinstance(feature["id"], str) and feature["id"].startswith("('way',"):
            osmid = int(feature["id"].split(",")[1].strip(" )"))
            feature["properties"]["osmid"] = osmid

    # Save the updated GeoJSON
    with open(output_file, "w") as f:
        geojson.dump(data, f, indent=2)


class OsmRoads:
    """
    A class for handling OpenStreetMap road data transformation.

    Args:
        polygon (shapely.geometry.Polygon):
            The polygon representing the area of interest.
        epsg_input (int, optional):
            The EPSG code of the input coordinate system. Defaults to 4326.
        epsg_output (int, optional):
            The EPSG code of the output coordinate system. Defaults to 31468.
    """

    def __init__(self, polygon, epsg_input=4326, epsg_output=25832):
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
            additional_tags (dict, optional):
                Additional tags to filter the road data. Defaults to None.

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
            "access",
        ]
        columns_to_keep = [col for col in columns_to_keep if col in osm_data.columns]
        osm_data = osm_data[columns_to_keep]
        return osm_data

    def save_roads(self, DOWNLOAD_FOLDER, epsg_code, additional_tags: dict = None):
        self.roads = self._get_roads(additional_tags)
        file_name = f"osm_data_{epsg_code}.geojson"
        file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
        with open(file_path, "w") as osm_file:
            geojson.dump(self.roads, osm_file)

        update_geojson_ids(file_path, file_path)

        return file_path

    def _osm_transform(self):
        osm_data = self.roads
        epsg_output = self.epsg_output
        # epsg_input = self.epsg_input
        osm_data = osm_data.to_crs(epsg=epsg_output)
        return osm_data
