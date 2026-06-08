"""Street selection domain logic.

The StreetSelector class encapsulates the load/modify/save/project cycle for
a job's street network. All user operations are stored declaratively in
``street_edits.json`` and re-derived from the immutable download file on
every change via :meth:`apply_edits`.

Note: ``apply_edits`` re-derives the full edited network from the download
file on every call. For large networks this may cause noticeable latency.
A debounce mechanism, deferred projection, or an explicit "Apply" button
could mitigate this in the future.
"""

from __future__ import annotations

import logging
import os

import orjson
from typing import TYPE_CHECKING

from shapely import STRtree
from shapely.geometry import box, mapping, shape
from sensor_routing.constants import OSM_FILENAME

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    OSM_TAGS_MAPPING,
    STREET_EDITS_FILE,
)
from cosmonaut_app.osm.projection import project_features_to_file
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_disconnected_roads,
)

if TYPE_CHECKING:
    from cosmonaut_app.cosmonaut_job import CosmonautJob

log = logging.getLogger(__name__)

_DEFAULT_TAGS = list(OSM_TAGS_MAPPING.keys())
# Properties the browser actually uses (style_handle, tooltips, click handler).
_DISPLAY_PROPERTIES = {"highway", "tooltip"}

# Module-level cache: avoids re-parsing large GeoJSON files on every callback.
# Keyed by absolute path → (mtime, features).  The download file is immutable
# within a job so its entry lives until the process restarts.  The edit file
# entry is refreshed every time _save_edit_file writes, so the viewport
# callback that fires right after never re-reads from disk.
_feature_cache: dict[str, tuple[float, list]] = {}


def _zoom_to_tolerance(zoom: float) -> float:
    """Map zoom level to simplification tolerance in degrees.

    Higher zoom → less simplification (user sees more detail).
    Lower zoom → more simplification (features are tiny anyway).
    """
    if zoom >= 15:
        return 0.00001  # ~1 m — near-original detail
    if zoom >= 13:
        return 0.0001  # ~11 m
    if zoom >= 11:
        return 0.0005  # ~55 m
    if zoom >= 9:
        return 0.001  # ~110 m
    return 0.005  # ~550 m — aggressive for overview


class StreetSelector:
    """Encapsulates street selection state and operations for a job.

    All edit state is persisted in ``street_edits.json`` with three keys:

    - ``removed_roads`` – list of feature IDs explicitly deleted by the user.
    - ``selected_road_tags`` – list of road-type labels currently enabled.
    - ``keep_largest`` – whether the keep-largest-component filter is active.

    Every mutating method calls :meth:`apply_edits` which re-derives
    ``osm_data_edited.geojson`` and ``osm_data_transformed.geojson`` from the
    immutable ``osm_data_download.geojson``.
    """

    def __init__(self, job: CosmonautJob):
        self.job = job
        self.download_path = os.path.join(job.working_dir, OSM_DATA_DOWNLOAD_FILE)
        self.edit_path = os.path.join(job.working_dir, OSM_DATA_EDITED_FILE)
        self.transformed_path = os.path.join(job.working_dir, OSM_FILENAME)
        self.edits_path = os.path.join(job.working_dir, STREET_EDITS_FILE)

        edits = self._load_edits()
        self.removed_roads: list[int] = edits["removed_roads"]
        self.selected_road_tags: list[str] = edits["selected_road_tags"]
        self.keep_largest_applied: bool = edits["keep_largest"]

    # -- public mutating methods ------------------------------------------

    def remove_roads(self, road_ids: list[int]) -> None:
        """Mark *road_ids* as deleted and re-derive the edited network."""
        unique_new = [
            rid for rid in dict.fromkeys(road_ids) if rid not in set(self.removed_roads)
        ]
        if not unique_new:
            return
        self.removed_roads.extend(unique_new)
        self.keep_largest_applied = False
        self.apply_edits(defer_projection=True)

    def restore_road(self, road_id: int) -> None:
        """Remove a single road ID from the removed list and re-derive."""
        if road_id not in self.removed_roads:
            return
        self.removed_roads.remove(road_id)
        self.keep_largest_applied = False
        self.apply_edits(defer_projection=True)

    def clear_removed_roads(self) -> None:
        """Clear the entire removed roads list and re-derive."""
        if not self.removed_roads:
            return
        self.removed_roads = []
        self.keep_largest_applied = False
        self.apply_edits(defer_projection=True)

    def update_tags(self, tags: list[str]) -> None:
        """Set the active road-type tags and re-derive the edited network."""
        self.selected_road_tags = tags
        self.keep_largest_applied = False
        self.apply_edits(defer_projection=True)

    def keep_largest(self) -> bool:
        """Activate the keep-largest-component filter.

        Returns False if the current network is empty (caller should guard).
        """
        self.keep_largest_applied = True
        return self.apply_edits(defer_projection=True)

    def reset(self) -> None:
        """Restore all edit state to defaults and re-derive."""
        self.removed_roads = []
        self.selected_road_tags = list(_DEFAULT_TAGS)
        self.keep_largest_applied = False
        self.apply_edits(defer_projection=True)

    # -- apply / derive ---------------------------------------------------

    def apply_edits(self, *, defer_projection: bool = False) -> bool:
        """Re-derive the edited network from the download baseline.

        Applies operations in order:
        1. Filter by ``selected_road_tags``
        2. Remove features in ``removed_roads``
        3. Optionally keep only the largest connected component

        When *defer_projection* is True the expensive reprojection step
        (``project_features_to_file``) is skipped.  The caller must invoke
        :meth:`ensure_projected` before the transformed file is needed
        (i.e. before routing).

        Returns False if the resulting feature set is empty.
        """
        features = self._load_download_features()
        features = self._filter_by_tags(features, self.selected_road_tags)
        removed_set = set(self.removed_roads)
        features = [f for f in features if f["id"] not in removed_set]

        if self.keep_largest_applied and features:
            G = build_graph(features)
            largest = get_largest_subnetwork(G)
            features = remove_disconnected_roads(G, largest, features)

        fc = {"type": "FeatureCollection", "features": features}
        self._save_edit_file(fc)
        if not defer_projection:
            if features:
                project_features_to_file(
                    features,
                    self.transformed_path,
                    src_epsg=4326,
                    dst_epsg=self.job.model.epsg,
                )
            else:
                self._save_edit_file(fc, path=self.transformed_path)
        self._save_edits()
        # Database must be current but skip rclone sync — interactive edits
        # (tag changes, road removals, keep-largest) happen frequently and the
        # rclone round-trip blocks the callback for seconds/minutes.  Files are
        # saved locally; MinIO is synced when the routing job is submitted.
        self.job.save(sync_files=False)

        log.info(
            "Applied edits: %d features, tags=%d, removed=%d, keep_largest=%s, deferred=%s",
            len(features),
            len(self.selected_road_tags),
            len(self.removed_roads),
            self.keep_largest_applied,
            defer_projection,
        )
        return bool(features)

    def ensure_projected(self) -> None:
        """Project the edited network to the job's EPSG if not up-to-date.

        Compares modification times: if the edited file is newer than the
        transformed file, reprojection is needed.  Safe to call multiple
        times — it's a no-op when the transformed file is already current.
        """
        if not os.path.exists(self.edit_path):
            return
        needs_projection = not os.path.exists(
            self.transformed_path
        ) or os.path.getmtime(self.edit_path) > os.path.getmtime(self.transformed_path)
        if not needs_projection:
            return
        features = self._load_edit_features()
        if features:
            project_features_to_file(
                features,
                self.transformed_path,
                src_epsg=4326,
                dst_epsg=self.job.model.epsg,
            )
        else:
            self._save_edit_file(
                {"type": "FeatureCollection", "features": []},
                path=self.transformed_path,
            )
        log.info("Projected %d features to EPSG %s", len(features), self.job.model.epsg)

    # -- read-only helpers ------------------------------------------------

    def visible_fc(self) -> dict:
        """Return a lightweight FeatureCollection for browser rendering.

        Adds tooltips, then strips unused properties and simplifies
        geometries so the payload is small and canvas rendering is fast.
        Only used as a fallback — prefer :meth:`viewport_fc` for map updates.
        """
        features = self._load_edit_features()
        self._add_tooltips(features)
        return {
            "type": "FeatureCollection",
            "features": self._simplify_for_display(features, _zoom_to_tolerance(12)),
        }

    def get_removed_roads_info(self) -> list[dict]:
        """Return display info for each removed road from the download file.

        Returns a list of dicts with keys: id, label (for display).
        """
        if not self.removed_roads or not os.path.exists(self.download_path):
            return []
        features = self._load_download_features()
        removed_set = set(self.removed_roads)
        result = []
        for f in features:
            if f["id"] in removed_set:
                props = f["properties"]
                # name and ref are optional OSM properties
                name = props.get("name") or props.get("ref")
                highway = props["highway"]
                label = (
                    f"{name} ({highway}) #{f['id']}"
                    if name
                    else f"{highway} #{f['id']}"
                )
                result.append({"id": f["id"], "label": label})
        return result

    def initial_fc(self) -> dict:
        """Return FeatureCollection for page load.

        Returns empty FeatureCollection if the edit file does not exist yet
        (e.g. street processing has not completed).
        """
        if not os.path.exists(self.edit_path):
            return {"type": "FeatureCollection", "features": []}
        return self.visible_fc()

    def viewport_fc(self, bounds: list, zoom: float) -> dict:
        """Return features visible in *bounds*, simplified for *zoom*.

        Args:
            bounds: Leaflet bounds ``[[south, west], [north, east]]``.
            zoom: Current map zoom level.

        Only features whose geometry intersects the viewport bounding box
        are included.  Geometries are simplified with a zoom-dependent
        tolerance so zoomed-out views are lightweight while zoomed-in
        views stay sharp.
        """
        if not os.path.exists(self.edit_path):
            return {"type": "FeatureCollection", "features": []}

        features = self._load_edit_features()
        self._add_tooltips(features)

        # Spatial filter — keep only features intersecting the viewport
        south, west = bounds[0]
        north, east = bounds[1]
        viewport_box = box(west, south, east, north)

        geometries = [shape(f["geometry"]) for f in features]
        tree = STRtree(geometries)
        indices = tree.query(viewport_box, predicate="intersects")
        visible = [features[i] for i in indices]

        tolerance = _zoom_to_tolerance(zoom)
        log.debug(
            "viewport_fc: %d/%d features visible at zoom=%.1f (tol=%.5f)",
            len(visible),
            len(features),
            zoom,
            tolerance,
        )
        return {
            "type": "FeatureCollection",
            "features": self._simplify_for_display(visible, tolerance),
        }

    # -- private I/O helpers ----------------------------------------------

    def _load_edits(self) -> dict:
        """Load street_edits.json or create it with defaults if missing."""
        defaults = {
            "removed_roads": [],
            "selected_road_tags": list(_DEFAULT_TAGS),
            "keep_largest": False,
        }
        if os.path.exists(self.edits_path):
            with open(self.edits_path, "rb") as f:
                return orjson.loads(f.read())
        # Create the file so it exists for future reads
        with open(self.edits_path, "wb") as f:
            f.write(orjson.dumps(defaults))
        return defaults

    def _save_edits(self) -> None:
        """Persist the current edit state to street_edits.json."""
        data = {
            "removed_roads": self.removed_roads,
            "selected_road_tags": self.selected_road_tags,
            "keep_largest": self.keep_largest_applied,
        }
        with open(self.edits_path, "wb") as f:
            f.write(orjson.dumps(data))

    def _load_download_features(self) -> list:
        return self._cached_load(self.download_path)

    def _load_edit_features(self) -> list:
        return self._cached_load(self.edit_path)

    @staticmethod
    def _cached_load(path: str) -> list:
        """Load features from *path*, returning a cached copy when fresh."""
        mtime = os.path.getmtime(path)
        cached = _feature_cache.get(path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with open(path, "rb") as f:
            features = orjson.loads(f.read())["features"]
        _feature_cache[path] = (mtime, features)
        return features

    def _save_edit_file(
        self, feature_collection: dict, path: str | None = None
    ) -> None:
        data = dict(feature_collection)
        data.pop("crs", None)
        target = path or self.edit_path
        with open(target, "wb") as f:
            f.write(orjson.dumps(data))
        # Warm the cache so the next _load_edit_features avoids a re-read.
        _feature_cache[target] = (os.path.getmtime(target), data["features"])

    @staticmethod
    def _add_tooltips(features: list) -> None:
        """Add tooltip property to each feature for map display."""
        for feat in features:
            properties = feat["properties"]
            # name and ref are optional OSM properties — not all roads have them
            name = properties.get("name") or properties.get("ref")
            highway = properties["highway"]
            properties["tooltip"] = f"{name}, {highway}" if name else highway

    @staticmethod
    def _simplify_for_display(features: list, tolerance: float) -> list:
        """Return lightweight copies of *features* for browser rendering.

        Strips all properties the client doesn't need and simplifies
        geometries so the JSON payload and canvas draw calls are smaller.
        The original feature list (and the files on disk) are untouched.
        """
        light = []
        for f in features:
            geom = shape(f["geometry"]).simplify(tolerance, preserve_topology=True)
            props = {
                k: v for k, v in f["properties"].items() if k in _DISPLAY_PROPERTIES
            }
            light.append(
                {
                    "id": f["id"],
                    "type": "Feature",
                    "geometry": mapping(geom),
                    "properties": props,
                }
            )
        return light

    @staticmethod
    def _filter_by_tags(features: list, selected_roads: list[str] | None) -> list:
        """Return features whose highway tag matches the selected road types."""
        if selected_roads is None:
            selected_roads = list(_DEFAULT_TAGS)
        osm_highway_types: set[str] = set()
        for road_type in selected_roads:
            if road_type in OSM_TAGS_MAPPING:
                osm_highway_types.update(OSM_TAGS_MAPPING[road_type])
        return [f for f in features if f["properties"]["highway"] in osm_highway_types]
