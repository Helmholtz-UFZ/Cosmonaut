#!/usr/bin/env python3
"""Measure and validate the Overpass-direct OSM backend.

Runs the backend in an isolated child process and reports peak RSS / time /
feature count / output size — the headline being Saxony-scale RAM. Optionally
diffs the output against a reference ``transformed.geojson`` (``--reference``) to
prove two runs/sources produce route-equivalent road networks: same osmid set,
identical ``nodes`` + routing tags, and an identical sensor-routing connectivity
graph.

The osmnx baseline this script originally compared against was removed together
with the osmnx dependency — that migration is proven in
docs/decisions/20260605-osm-overpass-direct-vs-osmnx.md. Use ``--reference`` with
a saved output to re-validate a new source (e.g. a future .pbf reader vs Overpass:
run each, save one, diff the other against it).

Usage:
    # Saxony-scale RAM against the local wiktorn (Saxony extract):
    python test/fixtures/compare_osm_backends.py \
        --membership ~/git/cache/sachsen/Saxony_..._membership_test.csv \
        --overpass-url http://localhost:12345/api --epsg 25832

    # Fidelity diff of this run against a saved reference network:
    python test/fixtures/compare_osm_backends.py \
        --reference /path/to/osm_data_transformed.geojson
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


def _classification_data(membership_path, epsg_input):
    """Build the Longitude/Latitude DataFrame the downloader expects."""
    frame = pd.read_csv(membership_path)
    easting = frame.iloc[:, 0].astype(float)
    northing = frame.iloc[:, 1].astype(float)
    transformer = Transformer.from_crs(epsg_input, 4326, always_xy=True)
    lon, lat = transformer.transform(easting.values, northing.values)
    return pd.DataFrame({"Longitude": lon, "Latitude": lat})


def _run_backend(membership_path, epsg, overpass_url, out_dir, queue):
    # Imported inside the child process (isolated peak-RSS measurement).
    from cosmonaut_app.osm import OsmDownloader
    from cosmonaut_app.osm.source import OverpassSource

    source = None
    if overpass_url:
        # osmnx-style base (…/api) -> Overpass interpreter endpoint.
        source = OverpassSource(overpass_url.rstrip("/") + "/interpreter")
    data = _classification_data(membership_path, epsg)
    start = time.time()
    OsmDownloader(data, epsg_output=epsg, source=source).run_osm_query(out_dir)
    queue.put(
        {
            "seconds": time.time() - start,
            "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        }
    )


def _run_isolated(target, *args):
    """Run the backend in a child process so peak RSS is measured in isolation."""
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


def _compare(reference, new):
    """Diff a reference network against the new output. Returns True if route-equivalent.

    only-in-REFERENCE ways mean the new run is missing data (alarming); only-in-NEW
    ways mean the new run adds data. Closed-way node-sequence rotation (same node
    SET) is routing-neutral.
    """
    ref_ids, new_ids = set(reference), set(new)
    only_ref, only_new = ref_ids - new_ids, new_ids - ref_ids
    print(f"  osmids: reference={len(ref_ids)} new={len(new_ids)} shared={len(ref_ids & new_ids)}")
    print(f"  ONLY in reference (new is missing): {len(only_ref)} -> {sorted(only_ref)[:10]}")
    print(f"  ONLY in new (new adds):             {len(only_new)} -> {sorted(only_new)[:10]}")

    set_mismatch, rotation_only, tag_mismatch, geom_max_delta = [], [], [], 0.0
    for osmid in ref_ids & new_ids:
        rp, np_ = reference[osmid]["properties"], new[osmid]["properties"]
        if set(rp["nodes"]) != set(np_["nodes"]):
            set_mismatch.append(osmid)
        elif rp["nodes"] != np_["nodes"]:
            rotation_only.append(osmid)  # same nodes, different start (closed way)
        for tag in ROUTING_TAGS:
            if rp[tag] != np_[tag]:
                tag_mismatch.append((osmid, tag, rp[tag], np_[tag]))
        rc, nc = reference[osmid]["geometry"]["coordinates"], new[osmid]["geometry"]["coordinates"]
        if rp["nodes"] == np_["nodes"] and len(rc) == len(nc):
            for (rx, ry), (nx, ny) in zip(rc, nc):
                geom_max_delta = max(geom_max_delta, abs(rx - nx), abs(ry - ny))

    print(f"  node-SET mismatches:      {len(set_mismatch)} -> {set_mismatch[:10]}")
    print(f"  closed-way rotation only: {len(rotation_only)} -> {rotation_only[:10]}")
    print(f"  routing-tag mismatches:   {len(tag_mismatch)} -> {tag_mismatch[:10]}")
    print(f"  max geom delta (aligned): {geom_max_delta:.6g} m")
    return not only_ref and not set_mismatch and not tag_mismatch


def main():
    parser = argparse.ArgumentParser()
    default_membership = os.path.join(os.path.dirname(__file__), "..", "memberships.csv")
    parser.add_argument("--membership", default=default_membership)
    parser.add_argument("--overpass-url", default="https://overpass-api.de/api",
                        help="osmnx-style base URL (…/api); /interpreter is appended")
    parser.add_argument("--epsg", type=int, default=25832)
    parser.add_argument("--reference",
                        help="transformed.geojson to diff the new output against")
    args = parser.parse_args()

    new_dir = tempfile.mkdtemp(prefix="osm_new_")
    print(f"AOI: {args.membership}")
    print(f"Overpass: {args.overpass_url}  EPSG:{args.epsg}\n")

    print("Running Overpass-direct backend (isolated)…")
    stats = _run_isolated(_run_backend, args.membership, args.epsg, args.overpass_url, new_dir)
    out_path = os.path.join(new_dir, OSM_FILENAME)
    out_mb = os.path.getsize(out_path) / (1024 * 1024)
    new_feats = _index_by_osmid(out_path)
    print(f"  {stats['seconds']:.1f}s, peak RSS {stats['max_rss_mb']:.0f} MB")
    print(f"  {len(new_feats)} road features, output {out_mb:.0f} MB -> {out_path}")

    if not args.reference:
        return

    print(f"\nFidelity vs reference {args.reference}:")
    ref_feats = _index_by_osmid(args.reference)
    features_ok = _compare(ref_feats, new_feats)

    print("\nRouting connectivity (sensor-routing node->roads map, shared roads):")
    shared_ids = set(ref_feats) & set(new_feats)
    ref_map = _shared_node_to_roads(ref_feats, shared_ids)
    new_map = _shared_node_to_roads(new_feats, shared_ids)
    connectivity_ok = ref_map == new_map
    print(f"  shared-graph nodes: reference={len(ref_map)} new={len(new_map)} "
          f"identical={connectivity_ok}")

    print("\n" + "=" * 60)
    verdict = "ROUTE-EQUIVALENT ✓" if (features_ok and connectivity_ok) else "DIFFERENCES FOUND ✗"
    print(f"VERDICT: {verdict}")
    print("=" * 60)
    sys.exit(0 if (features_ok and connectivity_ok) else 1)


if __name__ == "__main__":
    main()
