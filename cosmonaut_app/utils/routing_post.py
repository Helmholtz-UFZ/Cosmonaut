from __future__ import annotations

import io
import json
import logging
import os
import re
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from typing import List, Tuple, Dict, Any

from shapely.geometry import LineString, mapping
from pyproj import Transformer

log = logging.getLogger(__name__)


class _TeeLogger(io.TextIOBase):
    """File-like object used by redirect_stdout/redirect_stderr.
    - Immediately forwards allowed lines to logger at INFO
    - Accumulates all other text and logs it later at DEBUG
    """

    def __init__(
        self, logger: logging.Logger, prefix: str, allow_patterns: list[str] | None
    ):
        self.logger = logger
        self.prefix = prefix
        self.buf = ""  # current partial chunk
        self.suppressed = []  # lines not forwarded
        self.allow = [re.compile(p, re.IGNORECASE) for p in (allow_patterns or [])]

    def writable(self):
        return True

    def write(self, s: str):
        if not isinstance(s, str):
            s = str(s)
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self._handle_line(line.rstrip("\r"))
        return len(s)

    def flush(self):
        # handle leftover partial line
        if self.buf:
            self._handle_line(self.buf)
            self.buf = ""

    def _handle_line(self, line: str):
        if not line:
            return
        if any(p.search(line) for p in self.allow):
            self.logger.info("[%s] %s", self.prefix, line)
        else:
            self.suppressed.append(line)


@contextmanager
def silence_prints(
    prefix: str = "sensor-routing", info_patterns: list[str] | None = None
):
    """
    Redirect stdout/stderr from noisy libs.
    - Lines matching info_patterns are logged at INFO immediately.
    - Everything else is logged once at DEBUG when finished.
    """
    tee_out = _TeeLogger(log, prefix, info_patterns)
    tee_err = _TeeLogger(log, prefix, info_patterns)
    with redirect_stdout(tee_out), redirect_stderr(tee_err):
        yield
    tee_out.flush()
    tee_err.flush()
    if tee_out.suppressed:
        log.debug("[%s stdout suppressed]\n%s", prefix, "\n".join(tee_out.suppressed))
    if tee_err.suppressed:
        log.debug("[%s stderr suppressed]\n%s", prefix, "\n".join(tee_err.suppressed))


def _index_pairs_from_edges_geojson(
    edges_fc: Dict[str, Any],
) -> Dict[Tuple[int, int], List[Tuple[float, float]]]:
    """Build a lookup from consecutive node-id pairs to the full edge geometry coords (EPSG:25832)."""
    index: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
    features = edges_fc.get("features", [])
    for f in features:
        props = f.get("properties") or {}
        nodes = props.get("nodes") or props.get("node_ids") or []
        if not isinstance(nodes, list) or len(nodes) < 2:
            continue
        coords = f.get("geometry", {}).get("coordinates")
        if not coords:
            continue
        # normalize to list of (x, y)
        # GeoJSON can be either LineString or MultiLineString; we only expect LineString here.
        if f.get("geometry", {}).get("type") == "LineString":
            line_coords = [(float(x), float(y)) for x, y in coords]
        elif f.get("geometry", {}).get("type") == "MultiLineString":
            flat = []
            for part in coords:
                flat.extend([(float(x), float(y)) for x, y in part])
            line_coords = flat
        else:
            continue

        for i in range(len(nodes) - 1):
            u = int(nodes[i])
            v = int(nodes[i + 1])
            # Store both directions; reverse coordinates for (v, u)
            if (u, v) not in index:
                index[(u, v)] = line_coords
            if (v, u) not in index:
                index[(v, u)] = list(reversed(line_coords))
    return index


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_geojson(path: str, feature: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": [feature]}, f)


def build_solution_route_4326(workdir: str) -> str | None:
    """
    Build a 4326 LineString GeoJSON for the best route.

    It supports two kinds of solution.json["Path"]:
    - list of OSM node IDs (ints) -> we stitch edge geometries from input/osm_data_25832.geojson
    - list of [x, y] pairs in EPSG:25832 -> we connect them directly

    Returns: output file path or None if failed.
    """
    transient = os.path.join(workdir, "transient")
    sol_path = os.path.join(transient, "solution.json")
    if not os.path.isfile(sol_path):
        log.warning("No solution.json found at %s", sol_path)
        return None

    solution = _load_json(sol_path)
    path_seq = solution.get("Path") or []
    if not path_seq:
        log.warning("solution.json has no 'Path'")
        return None

    # Case 1: path is list of [x, y] coords in EPSG:25832
    if isinstance(path_seq[0], (list, tuple)) and len(path_seq[0]) == 2:
        coords_25832 = [(float(x), float(y)) for x, y in path_seq]
        line_25832 = LineString(coords_25832)
    else:
        # Case 2: path is list of OSM node IDs; stitch using edge geoms
        try:
            node_ids: List[int] = [
                int(n[0] if isinstance(n, list) else n) for n in path_seq
            ]
        except Exception:
            log.warning("Unsupported Path format; cannot build route geometry.")
            return None

        edges_path = None
        # prefer projected file with nodes/osmid present
        for candidate in (
            "osm_data_25832.geojson",
            "osm_data_work_4326.geojson",
            "osm_data_4326.geojson",
            "osm_data.geojson",
        ):
            p = os.path.join(workdir, candidate)
            if os.path.isfile(p):
                edges_path = p
                break
        if not edges_path:
            log.warning("No edges GeoJSON found in %s", workdir)
            return None

        edges_fc = _load_json(edges_path)
        pair_index = _index_pairs_from_edges_geojson(edges_fc)
        stitched: List[Tuple[float, float]] = []
        missing = 0
        for i in range(len(node_ids) - 1):
            pair = (node_ids[i], node_ids[i + 1])
            seg = pair_index.get(pair)
            if not seg:
                missing += 1
                continue
            # avoid duplicating the joint vertex
            if stitched and stitched[-1] == seg[0]:
                stitched.extend(seg[1:])
            else:
                stitched.extend(seg)
        if len(stitched) < 2:
            log.warning(
                "Could not reconstruct route geometry; missing segments=%d", missing
            )
            return None
        line_25832 = LineString(stitched)

    # Transform to 4326
    transformer = Transformer.from_crs(25832, 4326, always_xy=True)
    coords_4326 = [transformer.transform(x, y) for x, y in line_25832.coords]
    line_4326 = LineString(coords_4326)

    feature = {
        "type": "Feature",
        "geometry": mapping(line_4326),
        "properties": {
            "name": "Routing solution",
            "crs": "EPSG:4326",
            "distance": solution.get("Distance"),
            "time": solution.get("Time"),
            "benefit": solution.get("Benefit"),
        },
    }
    out_path = os.path.join(transient, "solution_route_4326.geojson")
    _save_geojson(out_path, feature)
    log.info("Wrote route layer: %s", out_path)
    return out_path
