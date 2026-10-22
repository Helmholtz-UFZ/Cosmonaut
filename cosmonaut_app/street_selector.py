"""Street selection domain logic.

The StreetSelector class encapsulates the load/modify/save/project cycle for
a job's street network. All user operations are stored declaratively as the
job's *intent* in the ``street_edits`` column of its row, and re-derived from
the immutable download file on every change via :meth:`apply_edits`.

The edited and projected GeoJSON are derived files (ADR 0001 in
cosmo-ecosystem): they may exist only on local disk until the job is submitted,
and are recomputed when missing or stale. A derived file is built from three
inputs, all named by the job's row: the intent, the EPSG, and the OSM download,
identified by the sha256 the upload worker records in
``membership_upload["download_sha256"]``. Their hash is the file's *source*.

``street_derived_hashes.json`` (the record) maps each derived file to its source
and to the sha256 of the file's own content. A file is current only if both
match: the source the row names now, and the bytes actually on disk. The row is
the authority, so a record left on another pod's disk can never make a file
built from an older download or intent look current, and clearing (a deleted
membership resets the download id) takes effect on every pod. The content
checksum binds the record to the file, so a pull that replaces one but not the
other also reads as stale. File checksums are cached per process by mtime and
size, so a freshness check normally costs a stat and a few bytes of JSON. A
sidecar rather than a property inside the GeoJSON so that check needs no parse
of a large network, and so the routing input carries no foreign member. Each
file's record is dropped before the file is rewritten and written after, so a
half-written file never looks current.

Note: ``apply_edits`` re-derives the full edited network from the download
file on every call. For large networks this may cause noticeable latency.
A debounce mechanism, deferred projection, or an explicit "Apply" button
could mitigate this in the future.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import orjson
from cosmo_ecosystem import job_persistence
from sensor_routing.constants import OSM_FILENAME
from shapely import STRtree
from shapely.geometry import box, mapping, shape

from cosmonaut_app.constants.general import (
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    OSM_TAGS_MAPPING,
    STREET_DERIVED_HASHES_FILE,
    STREET_EDITS_FILE,
    TRACK_GRADES,
    UNGRADED_TRACK_GRADE,
)
from cosmonaut_app.osm.projection import project_features_to_file
from cosmonaut_app.pydantic_models import StreetEdits
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_disconnected_roads,
    track_grade_allowed,
)

if TYPE_CHECKING:
    from cosmonaut_app.cosmonaut_job import CosmonautJob

log = logging.getLogger(__name__)

# Properties the browser actually uses (style_handle, tooltips, click handler).
_DISPLAY_PROPERTIES = {"highway", "tooltip"}

# Keyed by absolute path -> (mtime_ns, size, sha256).
_checksum_cache: dict[str, tuple[int, int, str]] = {}


def file_sha256(path: str) -> str:
    """Return the sha256 of the file at path, cached per process by mtime and size."""
    stat = os.stat(path)
    if path in _checksum_cache and _checksum_cache[path][:2] == (
        stat.st_mtime_ns,
        stat.st_size,
    ):
        return _checksum_cache[path][2]
    with open(path, "rb") as f:
        checksum = hashlib.file_digest(f, "sha256").hexdigest()
    _checksum_cache[path] = (stat.st_mtime_ns, stat.st_size, checksum)
    return checksum


def adopt_stored_download(job: CosmonautJob) -> None:
    """Record the checksum of the stored download for a job whose row lacks it.

    For downloads made before the upload worker recorded it, and for the race
    in which a status poll writes ``membership_upload`` back from a copy loaded
    before the worker's. Only acts when street processing is done and the
    checksum is missing; pulls the download (object storage wins) and writes
    the one column.
    """
    upload = job.model.membership_upload
    if upload["download_sha256"] is not None or upload["street_processing"] != (
        "COMPLETED"
    ):
        return
    path = job_persistence.pull_file(job.job_id, OSM_DATA_DOWNLOAD_FILE)
    if not os.path.exists(path):
        log.warning(f"Job {job.job_id} has street processing done but no download")
        return
    log.info(f"Adopt the stored OSM download of job {job.job_id} into its row")
    upload["download_sha256"] = file_sha256(path)
    job.update_columns("membership_upload")


def adopt_legacy_edits(job: CosmonautJob) -> None:
    """Move a job's intent from the legacy ``street_edits.json`` into its row.

    Jobs edited before the intent moved to the row keep it in that file, on
    local disk or (after a submit) in object storage. Only acts when the row has
    no intent yet and the file is in the local work dir; the file is then
    deleted everywhere so the row is the only copy. Call it before a pull where
    the local copy may be newer than the stored one (the old code kept edits
    local until submit), and again after the pull.
    """
    legacy_path = os.path.join(job.working_dir, STREET_EDITS_FILE)
    if job.model.street_edits is not None or not os.path.exists(legacy_path):
        return
    with open(legacy_path, "rb") as f:
        edits = orjson.loads(f.read())
    # Edit files written before the track-grade filter existed lack this key.
    # Those networks were downloaded without the default grade filter, so "all
    # grades" preserves the job's existing behaviour (unlike
    # DEFAULT_TRACK_GRADES, which would silently drop grade4/5 tracks).
    if "selected_track_grades" not in edits:
        edits["selected_track_grades"] = TRACK_GRADES + [UNGRADED_TRACK_GRADE]
    log.info(f"Adopt legacy street edits of job {job.model.job_id} into its row")
    job.model.street_edits = StreetEdits.model_validate(edits)
    job.update_columns("street_edits")
    job_persistence.delete_files(job.model.job_id, [STREET_EDITS_FILE])


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

    All edit state is the job's intent (:class:`StreetEdits`), persisted in
    the ``street_edits`` column of its row.

    Every mutating method calls :meth:`apply_edits` which writes the intent to
    the row and re-derives ``osm_data_edited.geojson`` (and, unless deferred,
    ``osm_data_transformed.geojson``) from the immutable
    ``osm_data_download.geojson``. :meth:`refresh` and :meth:`ensure_projected`
    recompute those derived files when they are missing or stale.
    """

    def __init__(self, job: CosmonautJob):
        self.job = job
        self.download_path = os.path.join(job.working_dir, OSM_DATA_DOWNLOAD_FILE)
        self.edit_path = os.path.join(job.working_dir, OSM_DATA_EDITED_FILE)
        self.transformed_path = os.path.join(job.working_dir, OSM_FILENAME)
        self.records_path = os.path.join(job.working_dir, STREET_DERIVED_HASHES_FILE)

        adopt_legacy_edits(job)
        self.edits = (
            StreetEdits()
            if job.model.street_edits is None
            else job.model.street_edits.model_copy(deep=True)
        )

    # -- intent, read-only for pages ----------------------------------------

    @property
    def removed_roads(self) -> list[int]:
        return self.edits.removed_roads

    @property
    def selected_road_tags(self) -> list[str]:
        return self.edits.selected_road_tags

    @property
    def selected_track_grades(self) -> list[str]:
        return self.edits.selected_track_grades

    @property
    def keep_largest_applied(self) -> bool:
        return self.edits.keep_largest

    # -- public mutating methods ------------------------------------------

    def remove_roads(self, road_ids: list[int]) -> None:
        """Mark *road_ids* as deleted and re-derive the edited network."""
        unique_new = [
            rid for rid in dict.fromkeys(road_ids) if rid not in set(self.removed_roads)
        ]
        if not unique_new:
            return
        self.edits.removed_roads.extend(unique_new)
        self.edits.keep_largest = False
        self.apply_edits(defer_projection=True)

    def restore_road(self, road_id: int) -> None:
        """Remove a single road ID from the removed list and re-derive."""
        if road_id not in self.removed_roads:
            return
        self.edits.removed_roads.remove(road_id)
        self.edits.keep_largest = False
        self.apply_edits(defer_projection=True)

    def clear_removed_roads(self) -> None:
        """Clear the entire removed roads list and re-derive."""
        if not self.removed_roads:
            return
        self.edits.removed_roads = []
        self.edits.keep_largest = False
        self.apply_edits(defer_projection=True)

    def update_tags(self, tags: list[str]) -> None:
        """Set the active road-type tags and re-derive the edited network."""
        # No-op when unchanged: reset_edits / select-all redeliver the same
        # checklist value, retriggering this path with identical state.
        if tags == self.selected_road_tags:
            return
        self.edits.selected_road_tags = tags
        self.edits.keep_largest = False
        self.apply_edits(defer_projection=True)

    def update_track_grades(self, grades: list[str]) -> None:
        """Set the allowed track grades and re-derive the edited network."""
        if grades == self.selected_track_grades:
            return
        self.edits.selected_track_grades = grades
        self.edits.keep_largest = False
        self.apply_edits(defer_projection=True)

    def keep_largest(self) -> bool:
        """Activate the keep-largest-component filter.

        Returns False if the current network is empty (caller should guard).
        """
        self.edits.keep_largest = True
        return self.apply_edits(defer_projection=True)

    def reset(self) -> None:
        """Restore all edit state to defaults and re-derive."""
        self.edits = StreetEdits()
        self.apply_edits(defer_projection=True)

    # -- apply / derive ---------------------------------------------------

    def apply_edits(self, *, defer_projection: bool = False) -> bool:
        """Write the intent to the job's row, then re-derive the edited network.

        One row write and, when this pod holds the download the row names, no
        object storage access: the derived files stay local until the job is
        submitted.

        Applies operations in order:
        1. Filter by ``selected_road_tags``
        2. Filter tracks by ``selected_track_grades``
        3. Remove features in ``removed_roads``
        4. Optionally keep only the largest connected component

        When *defer_projection* is True the expensive reprojection step
        (``project_features_to_file``) is skipped.  The caller must invoke
        :meth:`ensure_projected` before the transformed file is needed
        (i.e. before routing).

        Returns False if the resulting feature set is empty.
        """
        self.job.model.street_edits = self.edits.model_copy(deep=True)
        self.job.update_columns("street_edits")
        return self._derive(
            self._pull_download_if_other(), defer_projection=defer_projection
        )

    def _derive(self, download_sha256: str | None, *, defer_projection: bool) -> bool:
        """Write the derived files for the current intent; no row write.

        download_sha256 names the local download actually used. It differs
        from the row's only while object storage is ahead of the row (files are
        saved before the row); the record then reads as stale until they agree.
        """
        source = self._source(download_sha256)
        features = self._load_download_features()
        features = self._filter_by_tags(features, self.selected_road_tags)
        features = [
            f
            for f in features
            if track_grade_allowed(f["properties"], self.selected_track_grades)
        ]
        removed_set = set(self.removed_roads)
        features = [f for f in features if f["id"] not in removed_set]

        if self.keep_largest_applied and features:
            G = build_graph(features)
            largest = get_largest_subnetwork(G)
            features = remove_disconnected_roads(G, largest, features)

        fc = {"type": "FeatureCollection", "features": features}
        with self._rewriting(OSM_DATA_EDITED_FILE, source):
            self._save_edit_file(fc)
        if not defer_projection:
            self._project(features, source)

        log.info(
            "Applied edits: %d features, tags=%d, track_grades=%d, removed=%d, "
            "keep_largest=%s, deferred=%s",
            len(features),
            len(self.edits.selected_road_tags),
            len(self.edits.selected_track_grades),
            len(self.edits.removed_roads),
            self.edits.keep_largest,
            defer_projection,
        )
        return bool(features)

    def refresh(self) -> bool:
        """Make the edited network current; return whether there is one.

        Stale means built from another source than the row names: another
        intent, EPSG or download (see the module docstring). Recomputes a
        missing or stale file, pulling the download first if this pod's copy
        is not the one the row names. False, and nothing written, while the
        job has no download (street processing not done, or the membership
        deleted). No rclone call and no row write when the file is current.
        """
        download_sha256 = self._download_sha256()
        if download_sha256 is None:
            return False
        if self._is_current(OSM_DATA_EDITED_FILE, self._source(download_sha256)):
            return True
        local_download_sha256 = self._pull_download_if_other()
        if local_download_sha256 is None:
            return False
        log.info(f"Recompute the edited street network of job {self.job.job_id}")
        self._derive(local_download_sha256, defer_projection=True)
        return True

    def ensure_projected(self) -> None:
        """Make the edited and the projected network current with the intent.

        Recomputes the edited file first if needed (:meth:`refresh`), then
        projects it to the job's EPSG unless the projected file already matches
        the intent. Safe to call multiple times.
        """
        if not self.refresh():
            return
        # Projected from the edited file, so it shares that file's source.
        source = self._records()[OSM_DATA_EDITED_FILE]["source"]
        if self._is_current(OSM_FILENAME, source):
            return
        self._project(self._load_edit_features(), source)

    def _project(self, features: list, source: str) -> None:
        """Write *features* projected to the job's EPSG as the routing input."""
        with self._rewriting(OSM_FILENAME, source):
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

    def _download_sha256(self) -> str | None:
        """Return the checksum of the download the row names, or None."""
        adopt_stored_download(self.job)
        return self.job.model.membership_upload["download_sha256"]

    def _pull_download_if_other(self) -> str | None:
        """Make this pod's download the one the row names; return its checksum.

        Pulls (two rclone subprocesses) only when the local copy is missing or
        differs from the row's checksum. None if there is no download at all.
        """
        if self._local_download_sha256() != self._download_sha256():
            job_persistence.pull_file(self.job.job_id, OSM_DATA_DOWNLOAD_FILE)
        return self._local_download_sha256()

    def _local_download_sha256(self) -> str | None:
        if not os.path.exists(self.download_path):
            return None
        return file_sha256(self.download_path)

    def _source(self, download_sha256: str | None) -> str:
        """Hash what a derived file is built from: intent, EPSG and download."""
        source = {
            "intent": self.edits.model_dump(mode="json"),
            "epsg": self.job.model.epsg,
            "download_sha256": download_sha256,
        }
        return hashlib.sha256(
            orjson.dumps(source, option=orjson.OPT_SORT_KEYS)
        ).hexdigest()

    def _records(self) -> dict:
        """Return the record: derived file name -> {source, sha256}."""
        if not os.path.exists(self.records_path):
            return {}
        with open(self.records_path, "rb") as f:
            return orjson.loads(f.read())

    @contextmanager
    def _rewriting(self, file_name: str, source: str) -> Iterator[None]:
        """Drop file_name's record, let the caller rewrite the file, record it."""
        records = self._records()
        if file_name in records:
            del records[file_name]
            self._write_records(records)
        yield
        path = os.path.join(self.job.working_dir, file_name)
        records[file_name] = {"source": source, "sha256": file_sha256(path)}
        self._write_records(records)

    def _write_records(self, records: dict) -> None:
        with open(self.records_path, "wb") as f:
            f.write(orjson.dumps(records))

    def _is_current(self, file_name: str, source: str) -> bool:
        """Return whether the derived file_name exists, is built from source,
        and is the very file its record was written for."""
        path = os.path.join(self.job.working_dir, file_name)
        if not os.path.exists(path):
            return False
        records = self._records()
        # A record from before the download id (a bare string) never matches.
        return file_name in records and records[file_name] == {
            "source": source,
            "sha256": file_sha256(path),
        }

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
            selected_roads = list(OSM_TAGS_MAPPING)
        osm_highway_types: set[str] = set()
        for road_type in selected_roads:
            if road_type in OSM_TAGS_MAPPING:
                osm_highway_types.update(OSM_TAGS_MAPPING[road_type])
        return [f for f in features if f["properties"]["highway"] in osm_highway_types]
