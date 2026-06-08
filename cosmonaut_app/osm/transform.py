"""Transform raw OSM ways into the routing GeoJSON sensor-routing consumes.

This replaces the osmnx graph build/unbuild round-trip in
``cosmonaut_app.osm_downloader``. The output schema is the one documented in
docs/skills/local_sensor_routing.md (File 3): one LineString feature per OSM way
with a single integer ``osmid``, the ordered OSM ``nodes`` sequence (which alone
encodes routing connectivity), a normalized ``oneway``, and the highway tags.
"""

import logging

import numpy as np
import shapely

log = logging.getLogger(__name__)

# Output property order mirrors OsmDownloader.columns_to_keep (minus geometry),
# so the written GeoJSON matches the existing schema key-for-key. "osmid" and
# "nodes" are structural; everything else is read straight from the OSM tags.
PROPERTY_ORDER = [
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

# OSM oneway values osmnx treats as one-way (see osmnx.graph._is_path_one_way).
ONEWAY_TRUE_VALUES = {"yes", "true", "1", "-1"}


def _truncate_by_edge(nodes, coords, polygon):
    """Replicate osmnx ``truncate_by_edge``: keep every node-pair where at least
    one endpoint is inside the polygon, drop the rest.

    This bounds boundary ways to +1 node past the edge and preserves the
    nodes<->coords alignment exactly (whole nodes are trimmed from the ends;
    segments are never split, so no synthetic coordinate without a node id is
    introduced).

    Returns:
        (nodes, coords) trimmed to the single contiguous surviving run, or
        (None, None) if the way fragments into multiple runs — osmnx would yield
        a MultiLineString there, which the current pipeline drops.
    """
    xy = np.asarray(coords, dtype=float)
    # Vectorized point-in-polygon over the way's own nodes (per-way, transient —
    # no extra memory held vs the prior per-node shapely.Point objects). Honors
    # shapely.prepare(polygon) set once by the caller for a fast prepared index.
    inside = shapely.contains_xy(polygon, xy[:, 0], xy[:, 1])
    # Segment (i, i+1) survives if either endpoint is inside the polygon.
    keep = inside[:-1] | inside[1:]

    kept = np.flatnonzero(keep)
    if kept.size == 0:
        # Impossible via Overpass poly (>=1 inside node), guarded for direct use.
        return None, None
    first_segment, last_segment = int(kept[0]), int(kept[-1])
    if last_segment - first_segment + 1 != kept.size:
        # A gap between kept segments means the way left and re-entered the
        # polygon -> multiple runs -> fragmented -> dropped.
        return None, None

    # A run of segments [a..b] covers nodes [a .. b+1] inclusive.
    return nodes[first_segment : last_segment + 2], coords[first_segment : last_segment + 2]


def _infer_oneway(tags):
    """Determine oneway exactly as osmnx does for the non-bidirectional 'all'
    network: 'yes' if explicitly tagged one-way OR a roundabout, else 'no'.

    Mirrors osmnx.graph._is_path_one_way (rules 3 and 4) so the routing engine
    sees an identical is_oneway — including roundabouts, which OSM does not tag
    one-way explicitly but which osmnx (and thus the old pipeline) treats as
    one-way. osmnx also reverses geometry for oneway='-1'; those are rare and
    not reversed here (is_oneway parity holds either way).
    """
    if "oneway" in tags and tags["oneway"] in ONEWAY_TRUE_VALUES:
        return "yes"
    if "junction" in tags and tags["junction"] == "roundabout":
        return "yes"
    return "no"


def _build_properties(way_id, nodes, tags):
    """Assemble the feature properties in the canonical column order."""
    properties = {}
    for key in PROPERTY_ORDER:
        if key == "osmid":
            properties[key] = way_id
        elif key == "nodes":
            properties[key] = nodes
        elif key == "oneway":
            properties[key] = _infer_oneway(tags)
        else:
            # OSM tags are optional; null mirrors the osmnx missing-column output.
            properties[key] = tags[key] if key in tags else None
    return properties


def way_to_feature(way, polygon):
    """Transform one raw OSM way into a routing GeoJSON feature (EPSG:4326), or
    None if it fragments at the polygon boundary.

    Accepts ints/floats (stdlib json) or Decimals (streamed via ijson) and
    normalizes node ids to int and coordinates to float, so the output schema is
    identical regardless of the source/parser.

    The caller must have run ``shapely.prepare(polygon)`` once beforehand for fast
    point-in-polygon truncation.
    """
    coords = [(float(point["lon"]), float(point["lat"])) for point in way["geometry"]]
    nodes = [int(node) for node in way["nodes"]]
    nodes, coords = _truncate_by_edge(nodes, coords, polygon)
    if nodes is None:
        return None
    way_id = int(way["id"])
    return {
        "type": "Feature",
        "id": way_id,
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lon, lat in coords],
        },
        "properties": _build_properties(way_id, nodes, way["tags"]),
    }


def ways_to_features(ways, polygon):
    """Build routing GeoJSON features (EPSG:4326) from raw Overpass ways.

    Args:
        ways: Overpass ``way`` elements with ``id``, ``nodes``, ``geometry``, ``tags``.
        polygon: the 4326 query polygon, used for boundary truncation.

    Returns:
        list[dict]: GeoJSON LineString features ready for projection/export.
    """
    # Prepare the polygon's spatial index once; way_to_feature relies on it.
    shapely.prepare(polygon)

    features = [way_to_feature(way, polygon) for way in ways]
    features = [feature for feature in features if feature is not None]
    log.info("Built %d road features from %d ways", len(features), len(ways))
    return features
