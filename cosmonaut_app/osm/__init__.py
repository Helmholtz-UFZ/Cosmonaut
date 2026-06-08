"""Overpass-based OSM road-network download.

Replaces the former osmnx-based downloader (graph build/unbuild round-trip)
with a direct Overpass query. The routing
connectivity sensor-routing needs is carried by the native OSM ``nodes``
sequence, which Overpass returns directly — so no networkx graph is built.
"""

from cosmonaut_app.osm.downloader import OsmDownloader

__all__ = ["OsmDownloader"]
