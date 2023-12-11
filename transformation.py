"""
This script reads a csv file with coordinates in EPSG:31468 projection.
Then converts them to EPSG:4326 projection and calculates the bounding box of the projected csv file.
Out of this it creates a polygon from the bounding box, buffers the polygon, and queries the Overpass API to get the road network data of OSM inside the buffered polygon.
"""
import overpass
import time
import pandas as pd
import numpy as np
import pyproj
import overpass
import time
from shapely.geometry import Polygon
from pyproj import CRS, Transformer
import osmnx as ox
import osmnx as ox

# TODO use classes instead of functions
# TODO make functions for each step of the process

class CsvFile:
    def __init__(self, file_path, epsg_input, epsg_output):
        self.file_path = file_path
        self.epsg_input = epsg_input
        self.epsg_output = epsg_output
        self.df = self._transform_csv(epsg_input, epsg_output)

    def _transform_csv(self, crs_input, crs_output):
        """
        This function takes a CSV file as input, processes it and returns the result of a query to the Overpass API.

        Args:
            crs_input (str): The input CRS.
            crs_output (str): The output CRS.

        Returns:
            dict: A dictionary containing the result of the query to the Overpass API.

        """
        # crs_output = CRS.from_string(crs_output)
        # crs_input = CRS.from_string(crs_input)
        transformer = Transformer.from_crs(crs_input, crs_output)

        df = pd.read_csv(self.file_path)

        df["Latitude"], df["Longitude"] = transformer.transform(
            df["Easting (m)"].values, df["Northing (m)"].values
        )

        df.drop(
            ["Easting (m)", "Northing (m)"], axis=1, inplace=True
        )

        return df

    def get_convex_hull(self):
        points = self.df["Longitude", "Latitude"]
        hull = points.convex_hull
        hull_buffer = hull.buffer(0.005, cap_style="square", join_style=2)

        return hull_buffer
        
class OverpassQuery:
    def __init__(self, polygon):
        self.polygon = polygon
        self.query = self.get_query()
        self.result = self.get_result()
    
    # Query the Overpass API with the polygon and osmnx (features_from_polygon) amd make it so the user can choose the type of road network to download
    def get_query(self):
        ox.config(use_cache=True, log_console=True)
        tags = {
            'highway': ['primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'primary_link', 'secondary_link', 'tertiary_link', 'living_street', 'track', 'road']
        }
        osm_data = ox.geometries_from_polygon(self.polygon, tags=tags)
        return osm_data
    
    # Transform OSM data to csv EPSG
    def osm_transform(self):
        # Define EPSG.
        epsg_input = 4326
        epsg_output = 31468
        osm_data = self.osm_data

        
def transfrom_csv(input_file, epsg_input, epsg_output):
    """
    This function takes a CSV file as input, processes it and returns the result of a query to the Overpass API.

    Args:
        input_file (str): The path to the input CSV file.

    Returns:
        dict: A dictionary containing the result of the query to the Overpass API.

    """
    # Define EPSG.

    crs_output = CRS.from_epsg(epsg_output)
    crs_input = CRS.from_epsg(epsg_input)
    transformer = Transformer.from_crs(crs_input, crs_output)

    df = pd.read_csv(input_file)

    df["Latitude"], df["Longitude"] = transformer.transform(
        df["Easting (m)"].values, df["Northing (m)"].values
    )

    df.drop(
        ["Easting (m)", "Northing (m)"], axis=1, inplace=True
    )

    return df

def process_csv_file(input_file):
    """
    This function takes a CSV file as input, processes it and returns the result of a query to the Overpass API.

    Args:
        input_file (str): The path to the input CSV file.

    Returns:
        dict: A dictionary containing the result of the query to the Overpass API.

    """
    # Define EPSG.
    # TODO: Make the epsg customizable by the user
    crs_output = CRS.from_epsg(4326)
    crs_input = CRS.from_epsg(31468)
    transformer = Transformer.from_crs(crs_input, crs_output)

    df = pd.read_csv(input_file)

    df["Latitude"], df["Longitude"] = transformer.transform(
        df["Easting (m)"].values, df["Northing (m)"].values
    )

    df.drop(
        ["Easting (m)", "Northing (m)"], axis=1, inplace=True
    )  # axis=1 means columns, inplace=True means the changes are done in place and df is modified immediately

    min_lon = np.min(df["Longitude"])
    max_lon = np.max(df["Longitude"])
    min_lat = np.min(df["Latitude"])
    max_lat = np.max(df["Latitude"])

    # TODO: Make the polygon not as rectangle but as a polygon with the boundary of the coordinates
    polygon = Polygon(
        [(min_lon, min_lat), (min_lon, max_lat), (max_lon, max_lat), (max_lon, min_lat)]
    )

    polygon_buffer = polygon.buffer(0.005, cap_style="square", join_style=2)

    # extract the coordinates from the buffer and put them into a list

    polygon_buffer_coords = list(polygon_buffer.exterior.coords)
    polygon_buffer_coords = np.array(polygon_buffer_coords)

    buffered_min_lon = np.min(polygon_buffer_coords[:, 0])
    buffered_max_lon = np.max(polygon_buffer_coords[:, 0])
    buffered_min_lat = np.min(polygon_buffer_coords[:, 1])
    buffered_max_lat = np.max(polygon_buffer_coords[:, 1])

    # Query the Overpass API
    # TODO: use OSMNX instead of Overpass API
    # TODO make it so the user can choose the type of road network to download
    api = overpass.API(timeout=500)
    query = f"""
            // query part for: “highway=*”
            (way["highway"]({buffered_min_lat},{buffered_min_lon},{buffered_max_lat},{buffered_max_lon});
            );
        """

    for _ in range(5):  # Retry up to 5 times
        try:
            res = api.get(query, verbosity="geom", responseformat="geojson")
            print("Query run succesfuly")
            break
        except overpass.errors.ServerLoadError:
            print("Query failed, redoing it")
            time.sleep(1)  # Wait for 1 seconds before retrying

    # Transform OSM data to csv EPSG
    transformer = pyproj.Transformer.from_crs(crs_output, crs_input, always_xy=True)
    for feature in res["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Point":
            x, y = transformer.transform(
                geometry["coordinates"][0], geometry["coordinates"][1]
            )
            geometry["coordinates"] = [x, y]
        elif geometry["type"] == "LineString" or geometry["type"] == "MultiPoint":
            coords = geometry["coordinates"]
            geometry["coordinates"] = [transformer.transform(x, y) for x, y in coords]
        elif geometry["type"] == "Polygon" or geometry["type"] == "MultiLineString":
            rings = geometry["coordinates"]
            geometry["coordinates"] = [
                [transformer.transform(x, y) for x, y in ring] for ring in rings
            ]
        elif geometry["type"] == "MultiPolygon":
            polygons = geometry["coordinates"]
            geometry["coordinates"] = [
                [[transformer.transform(x, y) for x, y in ring] for ring in polygon]
                for polygon in polygons
            ]

    return res

    # roadata = process_csv_file(file_path)
    # with open("./download/test_31468.geojson", mode="w") as f:
    #     geojson.dump(roadata, f)
    #     print("OSM geojson file written")
