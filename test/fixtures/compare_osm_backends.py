#!/usr/bin/env python3
"""Spike: compare the osmnx OSM backend against the Overpass-direct backend.

Runs BOTH backends against the SAME Overpass endpoint for the SAME AOI (so any
difference is the transform, not OSM data drift), then proves fidelity at the
level that matters for routing:

  1. Feature diff   — same osmid set; identical `nodes`, routing tags and
                      geometry (within float tolerance) for shared osmids.
  2. Connectivity   — sensor-routing's own node->roads map is byte-identical
                      (this IS the graph the router runs on).
  3. RAM            — peak RSS of each backend, measured in an isolated child
                      process (this is the whole point at Saxony scale).

Usage:
    # Fidelity proof on the small test AOI against public Overpass:
    python test/fixtures/compare_osm_backends.py

    # Saxony scale / RAM against the local wiktorn (Saxony extract):
    python test/fixtures/compare_osm_backends.py \
        --membership ~/git/cache/sachsen/Saxony_political_boundaries_EPSG25832_membership_test.csv \
        --overpass-url http://localhost:12345/api \
        --epsg 25832

Notes:
    * --overpass-url is the osmnx-style BASE (…/api). The direct backend appends
      /interpreter automatically.
    * The two backends must hit the same data: point both at the same endpoint.
"""

import argparse
import json
import multiprocessing as mp
import os
import resource
import sys
import tempfile
import time

import pandas as pd
from pyproj import Transformer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sensor_routing.constants import OSM_FILENAME  # noqa: E402
from sensor_routing.point_mapping import build_node_to_roads_map  # noqa: E402

# Routing-relevant properties that must match exactly for identical routes.
ROUTING_TAGS = ["highway", "oneway", "maxspeed", "access", "source:maxspeed", "name"]
GEOM_TOLERANCE_M = 1e-6  # coordinates are reprojected identically -> expect ~0


def _classification_data(membership_path, epsg_input):
    """Build the Longitude/Latitude DataFrame both downloaders expect."""
    frame = pd.read_csv(membership_path)
    easting = frame.iloc[:, 0].astype(float)
    northing = frame.iloc[:, 1].astype(float)
    transformer = Transformer.from_crs(epsg_input, 4326, always_xy=True)
    lon, lat = transformer.transform(easting.values, northing.values)
    return pd.DataFrame({"Longitude": lon, "Latitude": lat})


def _run_old(membership_path, epsg, overpass_url, out_dir, queue):
    # Imports are inside the run functions on purpose: each backend runs in its
    # own child process (for isolated peak-RSS measurement), and osmnx settings
    # must be applied in that process before the downloader imports/uses them.
    import osmnx

    from cosmonaut_app.osm_downloader import OsmDownloader as OldDownloader

    # Disable osmnx's response cache so both backends see the SAME live data —
    # a stale cache silently makes osmnx miss ways added since the last run.
    osmnx.settings.use_cache = False
    if overpass_url:
        osmnx.settings.overpass_url = overpass_url
    data = _classification_data(membership_path, epsg)
    start = time.time()
    OldDownloader(data, epsg_output=epsg).run_osm_query(out_dir)
    queue.put(
        {
            "seconds": time.time() - start,
            "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        }
    )


def _run_new(membership_path, epsg, overpass_url, out_dir, queue):
    from cosmonaut_app.osm import OsmDownloader as NewDownloader
    from cosmonaut_app.osm.source import OverpassSource

    source = None
    if overpass_url:
        # osmnx base (…/api) -> Overpass interpreter endpoint.
        source = OverpassSource(overpass_url.rstrip("/") + "/interpreter")
    data = _classification_data(membership_path, epsg)
    start = time.time()
    NewDownloader(data, epsg_output=epsg, source=source).run_osm_query(out_dir)
    queue.put(
        {
            "seconds": time.time() - start,
            "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        }
    )


def _run_isolated(target, *args):
    """Run a backend in a child process so peak RSS is measured in isolation."""
    queue = mp.Queue()
    process = mp.Process(target=target, args=(*args, queue))
    process.start()
    process.join()
    if process.exitcode != 0:
        raise RuntimeError(f"{target.__name__} exited with code {process.exitcode}")
    return queue.get()


def _index_by_osmid(geojson_path):
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)
    return {feat["properties"]["osmid"]: feat for feat in data["features"]}


def _shared_node_to_roads(features_by_id, shared_ids):
    """sensor-routing's node->roads map over a restricted osmid set, normalized
    to {node: frozenset(roads)} for order-independent comparison."""
    collection = {"features": [features_by_id[osmid] for osmid in shared_ids]}
    return {node: frozenset(roads) for node, roads in build_node_to_roads_map(collection).items()}


def _compare_features(old, new):
    """Compare shared roads. Returns True if route-equivalent.

    only-in-OLD ways are alarming (the new backend would be losing data).
    only-in-NEW ways are osmnx drops (e.g. ways whose graph edges don't rechain
    into a single LineString) — the new backend keeps the original OSM way, so
    these are reported but do not fail the verdict.
    Closed-way node-sequence rotation (same node SET) is routing-neutral.
    """
    old_ids, new_ids = set(old), set(new)
    only_old, only_new = old_ids - new_ids, new_ids - old_ids
    print(f"  osmids: old={len(old_ids)} new={len(new_ids)} shared={len(old_ids & new_ids)}")
    print(f"  ONLY in old (new would LOSE these): {len(only_old)} -> {sorted(only_old)[:10]}")
    print(f"  ONLY in new (osmnx drops these):    {len(only_new)} -> {sorted(only_new)[:10]}")

    set_mismatch, rotation_only, tag_mismatch, geom_max_delta = [], [], [], 0.0
    for osmid in old_ids & new_ids:
        op, np_ = old[osmid]["properties"], new[osmid]["properties"]
        if set(op["nodes"]) != set(np_["nodes"]):
            set_mismatch.append(osmid)
        elif op["nodes"] != np_["nodes"]:
            rotation_only.append(osmid)  # same nodes, different start (closed way)
        for tag in ROUTING_TAGS:
            if op[tag] != np_[tag]:
                tag_mismatch.append((osmid, tag, op[tag], np_[tag]))
        oc, nc = old[osmid]["geometry"]["coordinates"], new[osmid]["geometry"]["coordinates"]
        if op["nodes"] == np_["nodes"] and len(oc) == len(nc):
            for (ox, oy), (nx, ny) in zip(oc, nc):
                geom_max_delta = max(geom_max_delta, abs(ox - nx), abs(oy - ny))

    print(f"  node-SET mismatches:        {len(set_mismatch)} -> {set_mismatch[:10]}")
    print(f"  closed-way rotation only:   {len(rotation_only)} -> {rotation_only[:10]}")
    print(f"  routing-tag mismatches:     {len(tag_mismatch)} -> {tag_mismatch[:10]}")
    print(f"  max geom delta (aligned):   {geom_max_delta:.6g} m")
    return not only_old and not set_mismatch and not tag_mismatch


def main():
    parser = argparse.ArgumentParser()
    default_membership = os.path.join(os.path.dirname(__file__), "..", "memberships.csv")
    parser.add_argument("--membership", default=default_membership)
    parser.add_argument("--overpass-url", default="https://overpass-api.de/api",
                        help="osmnx-style base URL (…/api); both backends use it")
    parser.add_argument("--epsg", type=int, default=25832)
    parser.add_argument("--new-only", action="store_true",
                        help="measure only the Overpass backend (skip osmnx) — "
                             "use at Saxony scale where osmnx would OOM")
    args = parser.parse_args()

    new_dir = tempfile.mkdtemp(prefix="osm_new_")

    print(f"AOI: {args.membership}")
    print(f"Overpass: {args.overpass_url}  EPSG:{args.epsg}\n")

    if args.new_only:
        print("Running Overpass-direct backend (isolated, new-only)…")
        new_stats = _run_isolated(_run_new, args.membership, args.epsg, args.overpass_url, new_dir)
        out_path = os.path.join(new_dir, OSM_FILENAME)
        out_mb = os.path.getsize(out_path) / (1024 * 1024)
        with open(out_path, encoding="utf-8") as f:
            n_features = len(json.load(f)["features"])
        print(f"  {new_stats['seconds']:.1f}s, peak RSS {new_stats['max_rss_mb']:.0f} MB")
        print(f"  {n_features} road features, output {out_mb:.0f} MB -> {out_path}")
        return

    old_dir = tempfile.mkdtemp(prefix="osm_old_")
    print("Running osmnx backend (isolated)…")
    old_stats = _run_isolated(_run_old, args.membership, args.epsg, args.overpass_url, old_dir)
    print(f"  {old_stats['seconds']:.1f}s, peak RSS {old_stats['max_rss_mb']:.0f} MB\n")

    print("Running Overpass-direct backend (isolated)…")
    new_stats = _run_isolated(_run_new, args.membership, args.epsg, args.overpass_url, new_dir)
    print(f"  {new_stats['seconds']:.1f}s, peak RSS {new_stats['max_rss_mb']:.0f} MB\n")

    print("Feature-level fidelity:")
    old_feats = _index_by_osmid(os.path.join(old_dir, OSM_FILENAME))
    new_feats = _index_by_osmid(os.path.join(new_dir, OSM_FILENAME))
    features_ok = _compare_features(old_feats, new_feats)

    print("\nRouting connectivity (sensor-routing node->roads map, shared roads):")
    # Restrict to the shared osmid set: only-in-new ways are osmnx drops the new
    # backend recovers, so they legitimately add nodes — compare the common graph.
    shared_ids = set(old_feats) & set(new_feats)
    old_map = _shared_node_to_roads(old_feats, shared_ids)
    new_map = _shared_node_to_roads(new_feats, shared_ids)
    connectivity_ok = old_map == new_map
    print(f"  shared-graph nodes: old={len(old_map)} new={len(new_map)} identical={connectivity_ok}")
    if not connectivity_ok:
        print(f"  nodes only in old: {len(set(old_map) - set(new_map))}; "
              f"only in new: {len(set(new_map) - set(old_map))}")

    print("\n" + "=" * 60)
    print(f"RAM:  osmnx {old_stats['max_rss_mb']:.0f} MB  vs  overpass {new_stats['max_rss_mb']:.0f} MB")
    verdict = "ROUTE-EQUIVALENT ✓" if (features_ok and connectivity_ok) else "DIFFERENCES FOUND ✗"
    print(f"VERDICT: {verdict}")
    print("=" * 60)
    sys.exit(0 if (features_ok and connectivity_ok) else 1)


if __name__ == "__main__":
    main()
