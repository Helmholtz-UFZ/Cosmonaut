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

import json
import logging
import os
from typing import TYPE_CHECKING

from sensor_routing.constants import OSM_FILENAME

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    OSM_TAGS_MAPPING,
    STREET_EDITS_FILE,
)
from cosmonaut_app.osm_downloader import project_and_save
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_disconnected_roads,
)

if TYPE_CHECKING:
    from cosmonaut_app.cosmonaut_job import CosmonautJob

log = logging.getLogger(__name__)

_DEFAULT_TAGS = list(OSM_TAGS_MAPPING.keys())


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
        self.apply_edits()

    def restore_road(self, road_id: int) -> None:
        """Remove a single road ID from the removed list and re-derive."""
        if road_id not in self.removed_roads:
            return
        self.removed_roads.remove(road_id)
        self.keep_largest_applied = False
        self.apply_edits()

    def clear_removed_roads(self) -> None:
        """Clear the entire removed roads list and re-derive."""
        if not self.removed_roads:
            return
        self.removed_roads = []
        self.keep_largest_applied = False
        self.apply_edits()

    def update_tags(self, tags: list[str]) -> None:
        """Set the active road-type tags and re-derive the edited network."""
        self.selected_road_tags = tags
        self.keep_largest_applied = False
        self.apply_edits()

    def keep_largest(self) -> bool:
        """Activate the keep-largest-component filter.

        Returns False if the current network is empty (caller should guard).
        """
        self.keep_largest_applied = True
        return self.apply_edits()

    def reset(self) -> None:
        """Restore all edit state to defaults and re-derive."""
        self.removed_roads = []
        self.selected_road_tags = list(_DEFAULT_TAGS)
        self.keep_largest_applied = False
        self.apply_edits()

    # -- apply / derive ---------------------------------------------------

    def apply_edits(self) -> bool:
        """Re-derive the edited network from the download baseline.

        Applies operations in order:
        1. Filter by ``selected_road_tags``
        2. Remove features in ``removed_roads``
        3. Optionally keep only the largest connected component

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
        if features:
            project_and_save(
                features,
                self.transformed_path,
                src_epsg=4326,
                dst_epsg=self.job.model.epsg,
            )
        else:
            self._save_edit_file(fc, path=self.transformed_path)
        self._save_edits()
        self.job.save()

        log.info(
            "Applied edits: %d features, tags=%d, removed=%d, keep_largest=%s",
            len(features),
            len(self.selected_road_tags),
            len(self.removed_roads),
            self.keep_largest_applied,
        )
        return bool(features)

    # -- read-only helpers ------------------------------------------------

    def visible_fc(self) -> dict:
        """Return the current edited FeatureCollection with tooltips added."""
        features = self._load_edit_features()
        self._add_tooltips(features)
        return {"type": "FeatureCollection", "features": features}

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

    # -- private I/O helpers ----------------------------------------------

    def _load_edits(self) -> dict:
        """Load street_edits.json or create it with defaults if missing."""
        defaults = {
            "removed_roads": [],
            "selected_road_tags": list(_DEFAULT_TAGS),
            "keep_largest": False,
        }
        if os.path.exists(self.edits_path):
            with open(self.edits_path, encoding="utf-8") as f:
                return json.load(f)
        # Create the file so it exists for future reads
        with open(self.edits_path, "w", encoding="utf-8") as f:
            json.dump(defaults, f, ensure_ascii=False)
        return defaults

    def _save_edits(self) -> None:
        """Persist the current edit state to street_edits.json."""
        data = {
            "removed_roads": self.removed_roads,
            "selected_road_tags": self.selected_road_tags,
            "keep_largest": self.keep_largest_applied,
        }
        with open(self.edits_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load_download_features(self) -> list:
        with open(self.download_path, encoding="utf-8") as f:
            return json.load(f)["features"]

    def _load_edit_features(self) -> list:
        with open(self.edit_path, encoding="utf-8") as f:
            return json.load(f)["features"]

    def _save_edit_file(
        self, feature_collection: dict, path: str | None = None
    ) -> None:
        data = dict(feature_collection)
        data.pop("crs", None)
        with open(path or self.edit_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

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
    def _filter_by_tags(features: list, selected_roads: list[str] | None) -> list:
        """Return features whose highway tag matches the selected road types."""
        if selected_roads is None:
            selected_roads = list(_DEFAULT_TAGS)
        osm_highway_types: set[str] = set()
        for road_type in selected_roads:
            if road_type in OSM_TAGS_MAPPING:
                osm_highway_types.update(OSM_TAGS_MAPPING[road_type])
        return [f for f in features if f["properties"]["highway"] in osm_highway_types]
