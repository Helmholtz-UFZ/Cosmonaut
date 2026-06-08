"""OSM data sources.

A source returns raw OpenStreetMap *ways* (with their native node-id sequence
and per-node geometry) for a polygon. Keeping this behind a small interface lets
us swap the backend — public/self-hosted Overpass now, a local ``.osm.pbf``
reader later — without touching the transform that builds the routing GeoJSON.
"""

import logging
import os

import ijson
import requests

log = logging.getLogger(__name__)

# Public Overpass is the default. Override with OVERPASS_URL to point at a
# self-hosted instance (wiktorn) or a UFZ-provided endpoint.
#
# Soft env lookup (not config.getenv) on purpose: the URL has a working default,
# so it must NOT become a required variable that test_env enforces across all
# five env files. Promote it to a strict config var only once the deployment
# story is settled (see docs/project-state.md, issue #36).
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_URL = os.getenv("OVERPASS_URL", DEFAULT_OVERPASS_URL)

# Server-side budget declared in the query, and the client read timeout.
# Saxony-sized queries against a self-hosted instance are fast; the public
# endpoint can be slow under load.
OVERPASS_QUERY_TIMEOUT = 180
OVERPASS_HTTP_TIMEOUT = 300

# A descriptive User-Agent is Overpass etiquette and is required by the public
# endpoint — overpass-api.de answers 406 to the default python-requests UA.
OVERPASS_HEADERS = {"User-Agent": "cosmonaut-osm (UFZ COSMONAUT route survey)"}


class OsmSource:
    """Source of raw OSM way elements for a polygon."""

    def fetch_ways(self, polygon, highway_types):
        """Return raw OSM way elements for the polygon.

        Args:
            polygon: shapely Polygon in EPSG:4326 (lon/lat).
            highway_types: OSM ``highway`` tag values to include.

        Returns:
            list[dict]: Overpass ``way`` elements, each with ``id``, ``nodes``,
            ``geometry`` (parallel to ``nodes``) and ``tags``.
        """
        raise NotImplementedError

    def stream_ways(self, polygon, highway_types):
        """Yield ways one at a time (memory-bounded download path).

        Default implementation falls back to the full ``fetch_ways`` list; a
        source that can parse incrementally (e.g. Overpass via ijson, or a ``.pbf``
        reader) overrides this to avoid holding the whole dataset in memory.
        """
        yield from self.fetch_ways(polygon, highway_types)


class OverpassSource(OsmSource):
    """Fetch ways from an Overpass endpoint via a single ``out geom`` query."""

    def __init__(self, overpass_url=OVERPASS_URL):
        self.overpass_url = overpass_url

    @staticmethod
    def _poly_clause(polygon):
        """Build the Overpass ``(poly:"lat lon ...")`` filter from a 4326 polygon."""
        # Overpass expects space-separated "lat lon" pairs of the exterior ring.
        return " ".join(f"{lat} {lon}" for lon, lat in polygon.exterior.coords)

    def _build_query(self, polygon, highway_types):
        # Same unanchored highway regex the old osmnx custom_filter used, so the
        # selected way set matches what osmnx fetched underneath.
        highway_regex = "|".join(highway_types)
        return (
            f"[out:json][timeout:{OVERPASS_QUERY_TIMEOUT}];"
            f'way["highway"~"{highway_regex}"]'
            f'(poly:"{self._poly_clause(polygon)}");'
            f"out geom;"
        )

    def fetch_ways(self, polygon, highway_types):
        """Return all matching ways as a list (parses the whole response).

        Convenient for small areas, tests, and the comparison script. For
        large-area downloads use ``stream_ways`` to bound memory.
        """
        query = self._build_query(polygon, highway_types)
        log.info(
            "Querying Overpass %s (%d highway types, %d poly vertices)",
            self.overpass_url,
            len(highway_types),
            len(polygon.exterior.coords),
        )
        response = requests.post(
            self.overpass_url,
            data={"data": query},
            headers=OVERPASS_HEADERS,
            timeout=OVERPASS_HTTP_TIMEOUT,
        )
        response.raise_for_status()
        ways = [e for e in response.json()["elements"] if e["type"] == "way"]
        log.info("Overpass returned %d ways", len(ways))
        return ways

    def stream_ways(self, polygon, highway_types):
        """Yield raw OSM way elements one at a time, parsing the response stream.

        Avoids materializing the whole Overpass response and its parsed object
        tree — the dominant RAM cost at large-area (Saxony) scale. Numbers come
        out as Decimals (ijson); the transform normalizes them to int/float.
        """
        query = self._build_query(polygon, highway_types)
        log.info(
            "Streaming Overpass %s (%d highway types, %d poly vertices)",
            self.overpass_url,
            len(highway_types),
            len(polygon.exterior.coords),
        )
        response = requests.post(
            self.overpass_url,
            data={"data": query},
            headers=OVERPASS_HEADERS,
            timeout=OVERPASS_HTTP_TIMEOUT,
            stream=True,
        )
        response.raise_for_status()
        response.raw.decode_content = True  # transparently inflate gzip/deflate
        for element in ijson.items(response.raw, "elements.item"):
            if element["type"] == "way":
                yield element
