"""Incremental, atomic GeoJSON FeatureCollection writer.

Writes features one at a time to disk so the OSM download never holds the whole
dataset (parsed response + all features + a GeoDataFrame) in memory at once —
this is what keeps the streaming download's peak RAM bounded.

Writes go to a ``<path>.tmp`` file and are renamed into place only on a clean
close, so a failed or partial download (e.g. an Overpass timeout mid-stream)
never leaves a half-written file behind. ``os.replace`` is a filesystem rename:
it costs no extra memory. See the decision record
docs/decisions/20260605-osm-overpass-direct-vs-osmnx.md.
"""

import json
import os


class StreamingGeoJsonWriter:
    """Append GeoJSON features to a FeatureCollection file incrementally and
    atomically.

    Args:
        path: final output file path. Written via ``path + ".tmp"`` and renamed
            into place on a clean close (same directory -> atomic rename).
        crs_epsg: if given, emit a named-CRS header (``EPSG::<code>``) matching the
            geopandas/GDAL output, so the projected file documents its CRS. Omit
            for plain 4326 files (the old pipeline wrote those without a header).

    Usage:
        with StreamingGeoJsonWriter(path, crs_epsg=25832) as writer:
            for feature in features:
                writer.write(feature)
        # On a clean exit the file is at `path`; on an exception nothing is left.
    """

    def __init__(self, path, crs_epsg=None):
        self._final_path = path
        self._tmp_path = path + ".tmp"
        self._file = open(self._tmp_path, "w", encoding="utf-8")
        self._first = True
        header = '{"type": "FeatureCollection", '
        if crs_epsg is not None:
            header += (
                '"crs": {"type": "name", "properties": '
                f'{{"name": "urn:ogc:def:crs:EPSG::{crs_epsg}"}}}}, '
            )
        header += '"features": ['
        self._file.write(header)

    def write(self, feature):
        if not self._first:
            self._file.write(", ")
        self._first = False
        json.dump(feature, self._file, ensure_ascii=False)

    def close(self):
        """Finalize the FeatureCollection and atomically move it into place."""
        self._file.write("]}")
        self._file.close()
        os.replace(self._tmp_path, self._final_path)

    def _discard(self):
        """Drop the partial temp file when the writer is abandoned on error."""
        self._file.close()
        if os.path.exists(self._tmp_path):
            os.remove(self._tmp_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.close()
        else:
            self._discard()
        return False  # never suppress the original exception
