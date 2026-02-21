import collections
import json
import logging
import os
import shutil

import geopandas as gpd
import numpy as np
import osmnx
from sensor_routing.constants import OSM_FILENAME
from shapely.geometry import Polygon
from shapely.ops import linemerge

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
)

log = logging.getLogger(__name__)


def project_and_save(features, dst_path, src_epsg, dst_epsg):
    """Project GeoJSON features to target CRS and save with CRS header."""
    gdf = gpd.GeoDataFrame.from_features(features, crs=f"EPSG:{src_epsg}")
    gdf = gdf.to_crs(epsg=dst_epsg)
    gdf.to_file(dst_path, driver="GeoJSON")


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
        if merged.geom_type == "MultiLineString":
            continue

        attrs = group.iloc[0].to_dict()
        for key in ("u", "v", "key", "geometry", "reversed", "length"):
            attrs.pop(key, None)

        attrs["nodes"] = node_sequence
        attrs["geometry"] = merged
        attrs["osmid"] = osmid
        rows.append(attrs)

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=edges_gdf.crs)


class OsmDownloader:
    """Download and project OpenStreetMap road data for a classification area.

    Args:
        classification_data: DataFrame with Longitude/Latitude columns.
        epsg_output: EPSG code of the target coordinate system.
    """

    columns_to_keep = [
        "geometry",
        "osmid",
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

    def __init__(self, classification_data, epsg_output=25832):
        self.polygon = self._get_convex_hull(classification_data)
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

    @staticmethod
    def _get_convex_hull(classification_data):
        """Calculate the convex hull of the given points and return a buffered polygon."""
        lon = classification_data.Longitude
        lat = classification_data.Latitude

        points = np.array([lon, lat]).T
        points = Polygon(points)
        hull = points.convex_hull
        hull_buffer = hull.buffer(0.005, cap_style="square", join_style=2)

        return hull_buffer

    @staticmethod
    def _ensure_feature_ids(features):
        """Assign stable integer ids if missing (selection relies on numeric ids)."""
        used = set()
        counter = 1
        for feat in features:
            fid = feat.get("id")
            if isinstance(fid, int) and fid not in used:
                used.add(fid)
                continue
            props = feat["properties"]
            candidates = [props.get("osmid"), props.get("id"), fid]
            chosen = None
            for c in candidates:
                if isinstance(c, int) and c not in used:
                    chosen = c
                    break
            if chosen is None:
                while counter in used:
                    counter += 1
                chosen = counter
                counter += 1
            feat["id"] = chosen
            used.add(chosen)
        return features

    @staticmethod
    def _normalize_for_routing(features):
        """Normalize oneway values for the routing engine."""
        for feat in features:
            props = feat["properties"]
            ow = props.get("oneway")
            if isinstance(ow, bool):
                props["oneway"] = "yes" if ow else "no"
            elif ow is not None:
                s = str(ow).lower()
                if s in ("1", "true", "yes"):
                    props["oneway"] = "yes"
                elif s in ("0", "false", "no", "-1"):
                    props["oneway"] = "no"

    def _get_roads(self, download_folder):
        """Get road data from OpenStreetMap using graph API to preserve node sequences."""
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

        # Save the 4326 download/edit files
        download_path = os.path.join(download_folder, OSM_DATA_DOWNLOAD_FILE)
        self.roads.to_file(download_path, driver="GeoJSON")

        # Assign stable IDs and normalize for routing on the saved GeoJSON
        with open(download_path, encoding="utf-8") as f:
            fc = json.load(f)
        self._ensure_feature_ids(fc["features"])
        self._normalize_for_routing(fc["features"])
        with open(download_path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False)

        edit_path = os.path.join(download_folder, OSM_DATA_EDITED_FILE)
        shutil.copy2(download_path, edit_path)

    def _osm_transform(self, download_folder):
        """Project the download file to the output CRS and save as the transformed file."""
        log.info("Transforming road data to EPSG:%s ...", self.epsg_output)
        download_path = os.path.join(download_folder, OSM_DATA_DOWNLOAD_FILE)
        with open(download_path, encoding="utf-8") as f:
            fc = json.load(f)

        project_and_save(
            fc["features"],
            os.path.join(download_folder, OSM_FILENAME),
            self.epsg_input,
            self.epsg_output,
        )

    def run_osm_query(self, download_folder):
        self._get_roads(download_folder)
        self._osm_transform(download_folder)
