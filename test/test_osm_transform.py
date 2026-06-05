"""Offline contract tests for the Overpass-based OSM transform.

Deterministic (no network, no services): feeds a committed raw Overpass
``out geom`` response through ``ways_to_features`` and asserts the output schema
sensor-routing relies on, the boundary-truncation logic, and that
sensor-routing's own ``build_node_to_roads_map`` consumes the result.

Fixture: ``test/fixtures/overpass_test_aoi.json`` — a real ``out geom`` query over
the test AOI bbox (lon 10.785-10.855, lat 51.937-51.988). Regenerate only if the
schema changes.
"""

import json
import os

from shapely.geometry import box

from cosmonaut_app.osm.transform import (
    PROPERTY_ORDER,
    _truncate_by_edge,
    ways_to_features,
)
from sensor_routing.point_mapping import build_node_to_roads_map

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "overpass_test_aoi.json")
# Bounding box the fixture was queried with (lon/lat), used for truncation.
AOI_BBOX = (10.7850, 51.9370, 10.8550, 51.9880)


def _load_features():
    with open(FIXTURE, encoding="utf-8") as f:
        ways = [e for e in json.load(f)["elements"] if e["type"] == "way"]
    return ways, ways_to_features(ways, box(*AOI_BBOX))


def test_transform_schema_contract():
    """Every feature carries the exact schema point_mapping reads."""
    ways, features = _load_features()
    assert features, "fixture produced no features"

    seen_ids = set()
    for feature in features:
        assert feature["geometry"]["type"] == "LineString"
        coords = feature["geometry"]["coordinates"]
        props = feature["properties"]

        # Connectivity carrier: nodes is an ordered list of ints, aligned to coords.
        nodes = props["nodes"]
        assert isinstance(nodes, list) and len(nodes) >= 2
        assert all(isinstance(n, int) for n in nodes)
        assert len(coords) == len(nodes)

        # osmid is a single int and unique across features.
        assert isinstance(props["osmid"], int)
        assert props["osmid"] not in seen_ids
        seen_ids.add(props["osmid"])

        # Properties present in canonical order; highway is the one always-set tag.
        assert list(props.keys()) == PROPERTY_ORDER
        assert props["highway"] is not None
        assert "name" in props  # sensor-routing reads name via direct access


def test_oneway_is_normalized():
    """oneway is inferred osmnx-style: always 'yes' or 'no', never None or a raw
    OSM value — and roundabouts come out 'yes' even without an explicit tag."""
    ways, features = _load_features()
    values = {feature["properties"]["oneway"] for feature in features}
    assert values <= {"yes", "no"}, f"unexpected oneway values: {values}"

    roundabout_ids = {
        way["id"]
        for way in ways
        if "junction" in way["tags"] and way["tags"]["junction"] == "roundabout"
    }
    for feature in features:
        if feature["properties"]["osmid"] in roundabout_ids:
            assert feature["properties"]["oneway"] == "yes"


def test_sensor_routing_consumes_nodes():
    """sensor-routing's own node->roads map builds from the output, with shared
    nodes producing real connectivity (more than one road on some node)."""
    _, features = _load_features()
    node_to_roads = build_node_to_roads_map({"features": features})

    assert node_to_roads, "no nodes mapped"
    assert all(isinstance(node, int) for node in node_to_roads)
    # A connected road network has junction nodes shared by multiple ways.
    assert any(len(roads) > 1 for roads in node_to_roads.values())


def test_truncate_by_edge_keeps_whole_way_inside():
    poly = box(0, 0, 10, 10)
    nodes = [1, 2, 3]
    coords = [(1, 1), (2, 2), (3, 3)]
    out_nodes, out_coords = _truncate_by_edge(nodes, coords, poly)
    assert out_nodes == nodes
    assert out_coords == coords


def test_truncate_by_edge_trims_to_one_node_past_boundary():
    poly = box(0, 0, 10, 10)
    nodes = [1, 2, 3, 4]
    coords = [(1, 1), (2, 2), (20, 20), (30, 30)]  # leaves at node 3
    out_nodes, out_coords = _truncate_by_edge(nodes, coords, poly)
    # Keeps the inside nodes plus exactly one node past the boundary (node 3).
    assert out_nodes == [1, 2, 3]
    assert out_coords == [(1, 1), (2, 2), (20, 20)]


def test_truncate_by_edge_drops_fragmented_way():
    poly = box(0, 0, 10, 10)
    nodes = [1, 2, 3, 4, 5, 6]
    # in, in, out, out, in, in -> two disjoint runs -> MultiLineString -> dropped
    coords = [(1, 1), (2, 2), (20, 20), (21, 21), (3, 3), (4, 4)]
    out_nodes, out_coords = _truncate_by_edge(nodes, coords, poly)
    assert out_nodes is None
    assert out_coords is None
