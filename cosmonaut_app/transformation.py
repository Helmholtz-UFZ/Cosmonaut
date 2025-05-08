import os
import csv
import geojson
import logging
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import CRS, Transformer
from shapely.geometry import Polygon

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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
    logger.info(f"Starting transformation of CSV file: {input_file}")

    if not input_file.endswith((".csv", ".txt")):
        logger.error("Input file must be a CSV or TXT file.")
        raise ValueError("Input file must be a CSV file.")

    # Use csv.Sniffer to detect delimiter
    try:
        with open(input_file, "r") as csvfile:
            sample = csvfile.read(4096)  # Read a sample to detect format
            dialect = csv.Sniffer().sniff(sample)
            has_header = csv.Sniffer().has_header(sample)
            delimiter = dialect.delimiter
        logger.info(f"Detected delimiter: '{delimiter}', Header: {has_header}")
    except Exception as e:
        logger.error(f"Error detecting CSV format: {e}")
        raise

    # Create transformer
    try:
        crs_input = CRS.from_epsg(epsg_input)
        crs_output = CRS.from_epsg(epsg_output)
        transformer = Transformer.from_crs(crs_input, crs_output)
        logger.info("Transformer successfully created.")
    except Exception as e:
        logger.error(f"Error creating CRS transformer: {e}")
        raise

    # Read the file with detected delimiter
    try:
        df = pd.read_csv(
            input_file, delimiter=delimiter, header=0 if has_header else None
        )
        logger.info(f"CSV file successfully read. Shape: {df.shape}")
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        raise

    # If no header, create default column names
    if not has_header:
        df.columns = [f"col_{i}" for i in range(len(df.columns))]
        logger.info("No header detected. Default column names assigned.")

    # Dynamically find coordinate columns
    potential_coord_cols = []
    for col in df.columns:
        if df[col].dtype.kind in "iuf":  # Only check numeric columns
            if (df[col].min() < 0 or df[col].max() > 1) and len(df[col].unique()) > 10:
                potential_coord_cols.append(col)

    try:
        if len(potential_coord_cols) == 2:
            x_col, y_col = potential_coord_cols
            logger.info(
                f"Automatically identified coordinate columns: {x_col}, {y_col}"
            )
        elif has_header:
            x_candidates = [
                col
                for col in df.columns
                if any(term in col.lower() for term in ["east", "long", "x", "lon"])
            ]
            y_candidates = [
                col
                for col in df.columns
                if any(term in col.lower() for term in ["north", "lat", "y"])
            ]

            if len(x_candidates) > 0 and len(y_candidates) > 0:
                x_col = x_candidates[0]
                y_col = y_candidates[0]
                logger.info(
                    f"Identified coordinate columns based on header: {x_col}, {y_col}"
                )
            else:
                logger.error("Could not automatically identify coordinate columns.")
                raise ValueError("Could not automatically identify coordinate columns.")
        else:
            logger.error("Could not automatically identify coordinate columns.")
            raise ValueError("Could not automatically identify coordinate columns.")
    except Exception as e:
        logger.error(f"Error identifying coordinate columns: {e}")
        raise

    # Transform coordinates
    try:
        df["Latitude"], df["Longitude"] = transformer.transform(
            df[x_col].values, df[y_col].values
        )
        logger.info("Coordinates successfully transformed.")
    except Exception as e:
        logger.error(f"Error transforming coordinates: {e}")
        raise

    # Drop original coordinate columns
    df.drop([x_col, y_col], axis=1, inplace=True)
    logger.info("Original coordinate columns dropped.")

    logger.info("CSV transformation completed successfully.")
    return df


def transform_solution(input_file, epsg_input, epsg_output, reversed_coords=False):
    """
    Transforms the coordinates of sensor-routing solution .json
    from one coordinate reference system (CRS) to another and
    converts the solution to GeoJSON format, preserving metadata.

    Args:
        input_file (str): Path to the solution.json file.
        epsg_input (int): Input EPSG code.
        epsg_output (int): Output EPSG code.
        reversed_coords (bool): Whether to reverse coordinates.

    Returns:
        dict: Transformed solution with metadata and features.
    """
    if not input_file.endswith(".json"):
        raise ValueError("Input file must be a .json file.")
    if not os.path.exists(input_file):
        raise FileNotFoundError("Input file does not exist.")

    with open(input_file, "r") as f:
        data = geojson.load(f)

    # Extract metadata
    metadata = {key: data[key] for key in data if key != "Path"}

    # Transform coordinates
    crs_output = CRS.from_epsg(epsg_output)
    crs_input = CRS.from_epsg(epsg_input)
    transformer = Transformer.from_crs(crs_input, crs_output)

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
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[start[1], start[0]], [end[1], end[0]]],
                },
                "properties": {"segment_index": i},
            }
        )

    # Include metadata and features
    geojson_data = {
        "type": "FeatureCollection",
        "metadata": metadata,
        "features": features,
    }

    # Save the transformed data to a new file
    output_file = os.path.join(os.path.dirname(input_file), "solution_transformed.json")
    with open(output_file, "w") as f:
        geojson.dump(geojson_data, f, indent=2)

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
        logger.info(
            f"OsmRoads initialized with EPSG input: {epsg_input}, EPSG output: {epsg_output}"
        )

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
            logger.debug(f"Additional tags provided: {additional_tags}")
        logger.info("Fetching road data from OpenStreetMap...")
        try:
            osm_data = ox.features_from_polygon(self.polygon, tags=self.tags)
            logger.info(
                f"Successfully fetched road data. Number of records: {len(osm_data)}"
            )
        except Exception as e:
            logger.error(f"Error fetching road data: {e}")
            raise

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
        logger.debug(f"Columns to keep: {columns_to_keep}")
        osm_data = osm_data[columns_to_keep]
        logger.info("Filtered road data to keep relevant columns.")
        return osm_data

    def save_roads(self, DOWNLOAD_FOLDER, epsg_code, additional_tags: dict = None):
        """
        Save the road data to a GeoJSON file.

        Args:
            DOWNLOAD_FOLDER (str): Path to the folder where the file will be saved.
            epsg_code (int): EPSG code for the output file.
            additional_tags (dict, optional): Additional tags for filtering road data.

        Returns:
            str: Path to the saved GeoJSON file.
        """
        logger.info("Saving road data...")
        try:
            self.roads = self._get_roads(additional_tags)
            file_name = f"osm_data_{epsg_code}.geojson"
            file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
            with open(file_path, "w") as osm_file:
                geojson.dump(self.roads, osm_file)
            logger.info(f"Road data saved to {file_path}")

            update_geojson_ids(file_path, file_path)
            logger.info("GeoJSON IDs updated successfully.")
        except Exception as e:
            logger.error(f"Error saving road data: {e}")
            raise

        return file_path

    def _osm_transform(self):
        """
        Transform the road data to the specified output CRS.

        Returns:
            geopandas.GeoDataFrame: Transformed road data.
        """
        logger.info("Transforming road data to the specified CRS...")
        try:
            osm_data = self.roads
            epsg_output = self.epsg_output
            osm_data = osm_data.to_crs(epsg=epsg_output)
            logger.info(f"Road data successfully transformed to EPSG: {epsg_output}")
        except Exception as e:
            logger.error(f"Error transforming road data: {e}")
            raise
        return osm_data
