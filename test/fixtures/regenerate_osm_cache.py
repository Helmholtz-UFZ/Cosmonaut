#!/usr/bin/env python3
"""Regenerate the OSM cache for integration tests.

This script runs the real OsmDownloader against the test AOI (test memberships.csv)
and caches the three output files. Run this only when the test AOI changes.

Usage:
    python test/fixtures/regenerate_osm_cache.py
"""

import os
import shutil
import tempfile

from cosmonaut_app.cosmonaut_job import _transform_csv
from cosmonaut_app.osm import OsmDownloader

CACHE_DIR = os.path.join(os.path.dirname(__file__), "osm_cache")
TEST_MEMBERSHIP_CSV = os.path.join(os.path.dirname(__file__), "..", "memberships.csv")


def regenerate():
    """Run OsmDownloader against the test AOI and cache outputs."""
    if not os.path.exists(TEST_MEMBERSHIP_CSV):
        raise FileNotFoundError(
            f"Test membership file not found: {TEST_MEMBERSHIP_CSV}"
        )

    csv_data = _transform_csv(TEST_MEMBERSHIP_CSV, epsg_input=25832, epsg_output=4326)

    with tempfile.TemporaryDirectory() as tmpdir:
        print("Running OsmDownloader with test AOI...")
        downloader = OsmDownloader(csv_data)
        downloader.run_osm_query(tmpdir)

        print(f"Caching outputs to {CACHE_DIR}...")
        for file_name in [
            "osm_data_download.geojson",
            "osm_data_edited.geojson",
            "osm_data_transformed.geojson",
        ]:
            src = os.path.join(tmpdir, file_name)
            dst = os.path.join(CACHE_DIR, file_name)
            if not os.path.exists(src):
                raise FileNotFoundError(f"Expected output not found: {file_name}")
            shutil.copy2(src, dst)
            print(f"  Cached: {file_name}")

    print("\n✓ Cache regenerated. Commit the changes:")
    print("  git add test/fixtures/osm_cache/")
    print("\nNote: Regenerate only when the test AOI (memberships.csv) changes.")


if __name__ == "__main__":
    regenerate()
