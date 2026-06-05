"""Transform raw OSM ways into the routing GeoJSON sensor-routing consumes.

This replaces the osmnx graph build/unbuild round-trip in
``cosmonaut_app.osm_downloader``. The output schema is the one documented in
docs/skills/local_sensor_routing.md (File 3): one LineString feature per OSM way
with a single integer ``osmid``, the ordered OSM ``nodes`` sequence (which alone
encodes routing connectivity), a normalized ``oneway``, and the highway tags.
"""

import logging

from shapely.geometry import Point

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
    inside = [polygon.contains(Point(lon, lat)) for lon, lat in coords]
    # Segment (i, i+1) survives if either endpoint is inside the polygon.
    keep = [inside[i] or inside[i + 1] for i in range(len(nodes) - 1)]

    runs = []
    current = []
    for i, keep_segment in enumerate(keep):
        if keep_segment:
            current.append(i)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)

    if len(runs) != 1:
        # 0 runs is impossible (Overpass poly guarantees >=1 inside node);
        # >1 run means the way left and re-entered the polygon -> fragmented.
        return None, None

    first_segment = runs[0][0]
    last_segment = runs[0][-1]
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


def ways_to_features(ways, polygon):
    """Build routing GeoJSON features (EPSG:4326) from raw Overpass ways.

    Args:
        ways: Overpass ``way`` elements with ``id``, ``nodes``, ``geometry``, ``tags``.
        polygon: the 4326 query polygon, used for boundary truncation.

    Returns:
        list[dict]: GeoJSON LineString features ready for projection/export.
    """
    features = []
    for way in ways:
        coords = [(point["lon"], point["lat"]) for point in way["geometry"]]
        nodes, coords = _truncate_by_edge(way["nodes"], coords, polygon)
        if nodes is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": way["id"],
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lon, lat in coords],
                },
                "properties": _build_properties(way["id"], nodes, way["tags"]),
            }
        )
    log.info("Built %d road features from %d ways", len(features), len(ways))
    return features
