"""OSM data sources.

A source returns raw OpenStreetMap *ways* (with their native node-id sequence
and per-node geometry) for a polygon. Keeping this behind a small interface lets
us swap the backend — public/self-hosted Overpass now, a local ``.osm.pbf``
reader later — without touching the transform that builds the routing GeoJSON.
"""

import json
import logging
import re

import ijson
import requests

from cosmonaut_app.config import OVERPASS_URL

log = logging.getLogger(__name__)

# Server-side budget declared in the query, and the client read timeout.
# Saxony-sized queries against a self-hosted instance are fast; the public
# endpoint can be slow under load.
OVERPASS_QUERY_TIMEOUT = 180
OVERPASS_HTTP_TIMEOUT = 300

# A descriptive User-Agent is Overpass etiquette and is required by the public
# endpoint — overpass-api.de answers 406 to the default python-requests UA.
OVERPASS_HEADERS = {"User-Agent": "cosmonaut-osm (UFZ COSMONAUT route survey)"}

# Overpass ends a response that failed server-side with a top-level ``remark``
# after the ``elements`` array, e.g. "runtime error: Query timed out in ..." or
# "runtime error: Query ran out of memory ...", while the HTTP status stays 200
# and ``elements`` holds whatever was collected so far. A way tag cannot imitate
# the pattern: quotes inside a JSON string are escaped.
_REMARK_AFTER_ELEMENTS = re.compile(r'\]\s*,\s*"remark"\s*:\s*("(?:[^"\\]|\\.)*")')
# The remark is a short sentence at the very end; this much of the stream's end
# is kept to find it without holding the response.
_TAIL_BYTES = 65536


class OverpassRuntimeError(Exception):
    """Overpass answered 200 but reported a server-side failure; the data is partial.

    Retryable: a timeout or out-of-memory depends on the server's load.
    """


class _TailKeepingReader:
    """File-like wrapper that remembers the last ``_TAIL_BYTES`` bytes read."""

    def __init__(self, raw):
        self._raw = raw
        self.tail = b""

    def read(self, size=-1):
        chunk = self._raw.read(size)
        self.tail = (self.tail + chunk)[-_TAIL_BYTES:]
        return chunk


def _raise_on_runtime_error(tail):
    """Raise OverpassRuntimeError if the end of the response carries a runtime error."""
    match = _REMARK_AFTER_ELEMENTS.search(tail.decode("utf-8", errors="replace"))
    if match is None:
        return
    remark = json.loads(match.group(1))
    if remark.startswith("runtime error"):
        raise OverpassRuntimeError(remark)
    log.warning(f"Overpass remark: {remark}")


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
        reader = _TailKeepingReader(response.raw)
        for element in ijson.items(reader, "elements.item"):
            if element["type"] == "way":
                yield element
        # Only now is the end of the response read: a partial result must not
        # pass as complete (the caller discards what it wrote on the exception).
        _raise_on_runtime_error(reader.tail)
