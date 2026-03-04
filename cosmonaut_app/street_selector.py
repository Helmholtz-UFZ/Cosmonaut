"""Street selection domain logic.

The StreetSelector class encapsulates the load/modify/save/project cycle for
a job's street network.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import TYPE_CHECKING

import networkx as nx
from sensor_routing.constants import OSM_FILENAME

from cosmonaut_app.constants.general import (
    JOB_STATUS_PENDING,
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    OSM_TAGS_MAPPING,
)
from cosmonaut_app.osm_downloader import project_and_save
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_dead_roads,
    remove_disconnected_roads,
)

if TYPE_CHECKING:
    from cosmonaut_app.cosmonaut_job import CosmonautJob

log = logging.getLogger(__name__)


class StreetSelector:
    """Encapsulates street selection state and operations for a job."""

    def __init__(self, job: CosmonautJob):
        self.job = job
        self.download_path = os.path.join(job.working_dir, OSM_DATA_DOWNLOAD_FILE)
        self.edit_path = os.path.join(job.working_dir, OSM_DATA_EDITED_FILE)
        self.transformed_path = os.path.join(job.working_dir, OSM_FILENAME)
        self._features: list | None = None

    @property
    def features(self) -> list:
        """Lazy-load features from edit file."""
        if self._features is None:
            with open(self.edit_path, encoding="utf-8") as f:
                data = json.load(f)
            self._features = data["features"]
        return self._features

    def is_pending(self) -> bool:
        """Return whether the job is in PENDING state."""
        return self.job.get_status() == JOB_STATUS_PENDING

    def remove_roads(self, road_ids: list) -> None:
        """Remove roads by ID, including dead-end cleanup."""
        unique_ids = list(dict.fromkeys(road_ids))
        features = self.features
        G = build_graph(features)
        for road_id in unique_ids:
            try:
                features = remove_dead_roads(road_id, features, G)
                G = build_graph(features)
            except (KeyError, nx.NetworkXError) as e:
                log.warning("remove_dead_roads failed for %s: %s", road_id, e)
        self._features = features

    def keep_largest(self, tag_filter: list) -> bool:
        """Keep only the largest subnetwork within the tag filter.

        Returns False if the filtered subset is empty (caller should guard).
        """
        features = self.features
        filtered_subset = self._filter_by_tags(features, tag_filter)
        log.info(
            "Largest-subnetwork on filtered subset: %d features", len(filtered_subset)
        )
        if not filtered_subset:
            return False

        G = build_graph(filtered_subset)
        largest = get_largest_subnetwork(G)
        kept_subset = remove_disconnected_roads(G, largest, filtered_subset)
        kept_ids = {f["id"] for f in kept_subset}
        log.info(
            "Kept %d/%d features in largest component for current filter",
            len(kept_subset),
            len(filtered_subset),
        )

        filtered_ids = {f["id"] for f in filtered_subset}
        new_features = []
        for f in features:
            fid = f["id"]
            if fid in filtered_ids:
                if fid in kept_ids:
                    new_features.append(f)
            else:
                new_features.append(f)

        self._features = new_features
        return True

    def reset(self) -> None:
        """Restore edited file from download baseline, prune disconnected roads, and regenerate export."""
        shutil.copy2(self.download_path, self.edit_path)
        self._features = None
        self.keep_largest(None)
        self.save()

    def save(self) -> None:
        """Write features to edit file and regenerate projected export."""
        features = self.features
        fc = {"type": "FeatureCollection", "features": features}
        self._save_edit_file(fc)
        project_and_save(
            features,
            self.transformed_path,
            src_epsg=4326,
            dst_epsg=self.job.model.epsg,
        )

    def visible_fc(self, tag_filter: list) -> dict:
        """Return a FeatureCollection filtered by tags with tooltips added."""
        visible = self._filter_by_tags(self.features, tag_filter)
        self._add_tooltips(visible)
        return {"type": "FeatureCollection", "features": visible}

    def initial_fc(self, tag_filter: list) -> dict:
        """Return initial FeatureCollection for page load.

        Returns empty FeatureCollection if the edit file does not exist yet.
        """
        if not os.path.exists(self.edit_path):
            return {"type": "FeatureCollection", "features": []}
        return self.visible_fc(tag_filter)

    def _save_edit_file(self, feature_collection: dict) -> None:
        data = dict(feature_collection)
        data.pop("crs", None)
        with open(self.edit_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @staticmethod
    def _add_tooltips(features: list) -> None:
        """Add tooltip property to each feature for map display."""
        for feat in features:
            properties = feat["properties"]
            name = properties.get("name") or properties.get("ref")
            highway = properties.get("highway")
            properties["tooltip"] = f"{name}, {highway}" if name else (highway or "")

    @staticmethod
    def _filter_by_tags(features: list, selected_roads: list | None) -> list:
        if selected_roads is None:
            selected_roads = list(OSM_TAGS_MAPPING.keys())
        osm_highway_types = set()
        for road_type in selected_roads:
            if road_type in OSM_TAGS_MAPPING:
                osm_highway_types.update(OSM_TAGS_MAPPING[road_type])
        return [
            f for f in features if f["properties"].get("highway") in osm_highway_types
        ]
