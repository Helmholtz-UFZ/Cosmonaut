import collections
import os
import csv
import geojson
import logging
import numpy as np
import osmnx
import pandas as pd
import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.ops import linemerge

all_osm_tags = {
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
    logging.info(f"Starting transformation of CSV file: {input_file}")

    if not input_file.endswith((".csv", ".txt")):
        logging.error("Input file must be a CSV or TXT file.")
        raise ValueError("Input file must be a CSV file.")

    # Use csv.Sniffer to detect delimiter
    with open(input_file, "r") as csvfile:
        sample = csvfile.read(4096)  # Read a sample to detect format
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
        delimiter = dialect.delimiter

    crs_input = CRS.from_epsg(epsg_input)
    crs_output = CRS.from_epsg(epsg_output)
    transformer = Transformer.from_crs(crs_input, crs_output)

    # Read the file with detected delimiter
    df = pd.read_csv(input_file, delimiter=delimiter, header=0 if has_header else None)

    # If no header, create default column names
    if not has_header:
        df.columns = [f"col_{i}" for i in range(len(df.columns))]

    # Dynamically find coordinate columns
    potential_coord_cols = []
    for col in df.columns:
        if df[col].dtype.kind in "iuf":  # Only check numeric columns
            if (df[col].min() < 0 or df[col].max() > 1) and len(df[col].unique()) > 10:
                potential_coord_cols.append(col)

    if len(potential_coord_cols) == 2:
        x_col, y_col = potential_coord_cols
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
        else:
            raise ValueError("Could not automatically identify coordinate columns.")
    else:
        raise ValueError("Could not automatically identify coordinate columns.")

    df["Latitude"], df["Longitude"] = transformer.transform(
        df[x_col].values, df[y_col].values
    )

    # Drop original coordinate columns
    df.drop([x_col, y_col], axis=1, inplace=True)

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


def get_bounds(classification_df):
    """
    Calculate the rectangular bounds of the given points.

    Returns:
        A list containing the minimum latitude, minimum longitude,
        maximum latitude, and maximum longitude.
    """
    lon = classification_df.Longitude
    lat = classification_df.Latitude

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


def _chain_edges(uv_pairs):
    """Reconstruct ordered node sequence from (u, v) edge pairs of a single way."""
    if not uv_pairs:
        return []
    if len(uv_pairs) == 1:
        return [uv_pairs[0][0], uv_pairs[0][1]]

    adjacency = collections.defaultdict(list)
    for u, v in uv_pairs:
        adjacency[u].append(v)
        adjacency[v].append(u)

    start = None
    for node, neighbors in adjacency.items():
        if len(neighbors) == 1:
            start = node
            break
    if start is None:
        start = uv_pairs[0][0]

    visited_edges = set()
    sequence = [start]
    current = start
    while True:
        moved = False
        for neighbor in adjacency[current]:
            edge = tuple(sorted((current, neighbor)))
            if edge not in visited_edges:
                visited_edges.add(edge)
                sequence.append(neighbor)
                current = neighbor
                moved = True
                break
        if not moved:
            break

    forward_set = set(uv_pairs)
    forward_count = sum(
        1
        for i in range(len(sequence) - 1)
        if (sequence[i], sequence[i + 1]) in forward_set
    )
    reverse_count = sum(
        1
        for i in range(len(sequence) - 1)
        if (sequence[i + 1], sequence[i]) in forward_set
    )
    if reverse_count > forward_count:
        sequence.reverse()

    return sequence


def _reconstruct_ways(edges_gdf):
    """Group graph edges by osmid and reconstruct per-way GeoDataFrame with node sequences."""
    edges_reset = edges_gdf.reset_index()
    forward_edges = edges_reset[edges_reset["reversed"] == False]  # noqa: E712

    rows = []
    for osmid, group in forward_edges.groupby("osmid"):
        uv_pairs = list(zip(group["u"], group["v"]))
        node_sequence = _chain_edges(uv_pairs)

        geom_lookup = {
            (row["u"], row["v"]): row["geometry"] for _, row in group.iterrows()
        }
        segments = []
        for i in range(len(node_sequence) - 1):
            pair = (node_sequence[i], node_sequence[i + 1])
            if pair in geom_lookup:
                segments.append(geom_lookup[pair])

        if not segments:
            continue

        merged = linemerge(segments) if len(segments) > 1 else segments[0]

        attrs = group.iloc[0].to_dict()
        for key in ("u", "v", "key", "geometry", "reversed", "length"):
            attrs.pop(key, None)

        attrs["nodes"] = node_sequence
        attrs["geometry"] = merged
        attrs["osmid"] = osmid
        rows.append(attrs)

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=edges_gdf.crs)


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
    roads: gpd.GeoDataFrame
    roads_transformed: gpd.GeoDataFrame

    def __init__(self, classification_data, epsg_output=25832):
        self.polygon = get_convex_hull(classification_data)
        self.tags = {
            "highway": [
                "motorway",
                "primary",
                "secondary",
                "tertiary",
                "unclassified",
                "residential",
                "living_street",
                "track",
            ]
        }
        self.epsg_input = 4326
        self.epsg_output = epsg_output

    def _get_roads(self, download_folder):
        """
        Get road data from OpenStreetMap using graph API to preserve node sequences.
        """
        osmnx.settings.useful_tags_way = [
            "access",
            "area",
            "bicycle",
            "bridge",
            "est_width",
            "highway",
            "junction",
            "landuse",
            "lanes",
            "lanes:backward",
            "lit",
            "maxspeed",
            "motor_vehicle",
            "name",
            "oneway",
            "ref",
            "service",
            "sidewalk",
            "smoothness",
            "source:maxspeed",
            "surface",
            "tracktype",
            "traffic_calming",
            "tunnel",
            "width",
        ]

        highway_types = "|".join(self.tags["highway"])
        custom_filter = f'["highway"~"{highway_types}"]'

        G = osmnx.graph_from_polygon(
            self.polygon,
            network_type="all",
            simplify=False,
            retain_all=True,
            truncate_by_edge=True,
            custom_filter=custom_filter,
        )

        edges_gdf = osmnx.convert.graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
        ways_gdf = _reconstruct_ways(edges_gdf)

        columns_to_keep = [
            col for col in self.columns_to_keep if col in ways_gdf.columns
        ]
        self.roads = ways_gdf[columns_to_keep]

        file_path = os.path.join(download_folder, "osm_data.geojson")
        self.roads.to_file(file_path, driver="GeoJSON")

    def _osm_transform(self, download_folder):
        """
        Transform the road data to the specified output CRS.

        Returns:
            geopandas.GeoDataFrame: Transformed road data.
        """
        logging.info("Transforming road data to the specified CRS...")
        self.roads_transformed = self.roads.to_crs(epsg=self.epsg_output)
        self.roads_transformed["nodes"] = self.roads_transformed["nodes"].apply(str)
        self.roads_transformed.to_file(
            os.path.join(download_folder, "osm_data_transformed.geojson"),
            driver="GeoJSON",
        )

    def run_osm_query(self, download_folder):
        self._get_roads(download_folder)
        self._osm_transform(download_folder)
