"""Utility functions for Street Selection feature.

Separated from page and callback definitions to keep UI files clean.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from typing import List, Dict, Any

import geojson

from cosmonaut_app.config import osm_tags_mapping, WEB_WORK_DIR
from cosmonaut_app.transformation import transform_geojson

# Public API (keep narrow; callbacks import these)
__all__ = [
    "paths",
    "load_fc",
    "ensure_feature_ids",
    "filter_by_tags",
    "save_fc_4326_no_crs",
    "snapshot_work_copy",
    "coerce_nodes_list",
    "normalize_for_sensor_routing",
    "export_projected_geojson",
    "safe_projected_export",
]


def paths(job_id: str) -> tuple[str, str, str]:
    """Return (in_dir, raw_path, work_path).

    raw_path: baseline osm_data.geojson
    work_path: editable copy (created lazily on first edit)
    """
    in_dir = os.path.join(WEB_WORK_DIR, job_id, "input")
    raw_path = os.path.join(in_dir, "osm_data.geojson")
    work_path = os.path.join(in_dir, "osm_data_work_4326.geojson")
    return in_dir, raw_path, work_path


def load_fc(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_feature_ids(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assign stable integer ids if missing (selection relies on numeric ids)."""
    used = set()
    counter = 1
    for feat in features:
        fid = feat.get("id")
        if isinstance(fid, int) and fid not in used:
            used.add(fid)
            continue
        props = feat.get("properties") or {}
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


def initial_features(job_id) -> List[Dict[str, Any]]:
    # Build map with a pre-mounted empty (or preloaded) GeoJSON layer we will update via
    # callbacks. Attempt initial data load so user sees network immediately if files
    # exist.
    initial_fc = {"type": "FeatureCollection", "features": []}
    # TODO job dirs ar now attributes
    in_dir, raw_path, work_path = paths(job_id)
    source = work_path if os.path.exists(work_path) else raw_path
    if source and os.path.exists(source):
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
        feats = data.get("features", [])
        ensure_feature_ids(feats)
        feats = filter_by_tags(feats, list(osm_tags_mapping.keys()))
        for feat in feats:
            p = feat.setdefault("properties", {})
            name = p.get("name") or p.get("ref")
            hw = p.get("highway")
            p["tooltip"] = f"{name}, {hw}" if name else f"{hw}"
        initial_fc = {"type": "FeatureCollection", "features": feats}

    return initial_fc


def filter_by_tags(
    features: List[Dict[str, Any]], selected_roads: List[str] | None
) -> List[Dict[str, Any]]:
    # None -> all tags; empty list -> no features
    if selected_roads is None:
        selected_roads = list(osm_tags_mapping.keys())
    osm_highway_types = set()
    for german_type in selected_roads:
        if german_type in osm_tags_mapping:
            osm_highway_types.update(osm_tags_mapping[german_type])
    return [
        f
        for f in features
        if (f.get("properties") or {}).get("highway") in osm_highway_types
    ]


def save_fc_4326_no_crs(path: str, feature_collection: Dict[str, Any]) -> None:
    data = dict(feature_collection)
    data.pop("crs", None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def snapshot_work_copy(in_dir: str, work_4326: str) -> str | None:
    """Save timestamped backup before modifying work file."""
    try:
        if os.path.exists(work_4326):
            hist_dir = os.path.join(in_dir, "history")
            os.makedirs(hist_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            dst = os.path.join(hist_dir, f"osm_data_work_4326_{ts}.geojson")
            shutil.copy2(work_4326, dst)
            return dst
    except Exception as e:
        logging.warning("Snapshot failed: %s", e)
    return None


def coerce_nodes_list(features: List[Dict[str, Any]]) -> None:
    for f in features:
        nodes = f.get("properties", {}).get("nodes")
        if isinstance(nodes, str):
            try:
                nodes = json.loads(nodes)
            except Exception:
                nodes = []
            f["properties"]["nodes"] = nodes


def normalize_for_sensor_routing(features: List[Dict[str, Any]]) -> None:
    def _coerce_osmid(props: Dict[str, Any], fallback_id: Any, fallback: int) -> int:
        for c in (props.get("osmid"), props.get("id"), fallback_id):
            if isinstance(c, int):
                return c
        return fallback

    missing = 0
    for i, feat in enumerate(features):
        props = feat.get("properties") or {}
        osmid = _coerce_osmid(props, feat.get("id"), fallback=i + 1)
        if "osmid" not in props:
            missing += 1
        props["osmid"] = osmid
        nodes = props.get("nodes")
        if isinstance(nodes, str):
            try:
                nodes = json.loads(nodes)
            except Exception:
                nodes = [int(n) for n in re.findall(r"-?\d+", nodes)]
            props["nodes"] = nodes
        if isinstance(props.get("nodes"), (list, tuple)):
            try:
                props["nodes"] = [int(n) for n in props["nodes"]]
            except Exception:
                pass
        ow = props.get("oneway")
        if isinstance(ow, bool):
            props["oneway"] = "yes" if ow else "no"
        elif ow is not None:
            s = str(ow).lower()
            if s in ("1", "true", "yes"):
                props["oneway"] = "yes"
            elif s in ("0", "false", "no", "-1"):
                props["oneway"] = "no"
        feat["properties"] = props
    logging.info(
        "Normalized %d features; added osmid to %d features", len(features), missing
    )


def export_projected_geojson(
    in_dir: str, work_4326: str, epsg_input: int | str | None
) -> None:
    if not epsg_input:
        return
    try:
        transformed = transform_geojson(work_4326, 4326, epsg_input)
        feats = transformed.get("features", [])
        coerce_nodes_list(feats)
        normalize_for_sensor_routing(feats)
        transformed = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_input}"},
            },
            "features": feats,
        }
        out_path = os.path.join(in_dir, f"osm_data_{epsg_input}.geojson")
        with open(out_path, "w", encoding="utf-8") as f:
            geojson.dump(transformed, f)
    except Exception as e:
        logging.warning("Failed to write projected export: %s", e)


def safe_projected_export(
    in_dir: str, work_4326: str, epsg_input: int | str | None
) -> None:
    """Wrapper used by page callbacks to reduce repeated try/except blocks.

    Delegates to export_projected_geojson and logs any exception uniformly.
    """
    try:
        export_projected_geojson(in_dir, work_4326, epsg_input)
    except Exception as e:  # pragma: no cover - defensive catch
        logging.warning("Projected export failed (ignored): %s", e)
