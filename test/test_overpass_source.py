"""OverpassSource.stream_ways against a fake HTTP response (no network).

Overpass reports a server-side failure in-band: HTTP 200 and a top-level
``remark`` key after the (partial) ``elements`` array.
"""

import io
import json
import unittest.mock as mock

import ijson
import pytest
import shapely.geometry

from cosmonaut_app.osm.source import OverpassRuntimeError, OverpassSource

POLYGON = shapely.geometry.box(10.0, 50.0, 10.1, 50.1)


def _way(way_id):
    return {
        "type": "way",
        "id": way_id,
        "nodes": [1, 2],
        "geometry": [{"lat": 50.0, "lon": 10.0}, {"lat": 50.1, "lon": 10.1}],
        "tags": {"highway": "residential"},
    }


class _FakeResponse:
    """The parts of requests.Response that stream_ways uses."""

    def __init__(self, body):
        self.raw = io.BytesIO(body)
        self.decode_content = False

    def raise_for_status(self):
        pass


def _overpass_json(elements, remark=None, indent=None):
    document = {"version": 0.6, "generator": "Overpass API", "elements": elements}
    if remark is not None:
        # Overpass writes the remark after the elements array.
        document["remark"] = remark
    return json.dumps(document, indent=indent).encode()


def _stream(body):
    with mock.patch(
        "cosmonaut_app.osm.source.requests.post", return_value=_FakeResponse(body)
    ):
        return list(OverpassSource("http://overpass.test").stream_ways(POLYGON, ["x"]))


def test_a_complete_response_yields_its_ways():
    ways = _stream(_overpass_json([_way(1), {"type": "node", "id": 9}, _way(2)]))

    assert [w["id"] for w in ways] == [1, 2]


@pytest.mark.parametrize("indent", [None, 2])
@pytest.mark.parametrize(
    "remark",
    [
        'runtime error: Query timed out in "query" at line 1 after 181 seconds.',
        "runtime error: Query ran out of memory using about 2048 MB of RAM.",
    ],
)
def test_an_in_band_runtime_error_raises_instead_of_ending_the_stream(remark, indent):
    body = _overpass_json([_way(1), _way(2)], remark=remark, indent=indent)

    with pytest.raises(OverpassRuntimeError, match="runtime error"):
        _stream(body)


def test_the_remark_is_found_after_a_response_larger_than_the_tail_window():
    ways = [_way(i) for i in range(5000)]
    body = _overpass_json(ways, remark="runtime error: Query timed out")
    assert len(body) > 4 * 65536

    with pytest.raises(OverpassRuntimeError):
        _stream(body)


def test_a_way_tag_that_mentions_remark_is_not_an_error():
    way = _way(1)
    way["tags"]["note"] = '], "remark": "runtime error: not a remark"'

    assert [w["id"] for w in _stream(_overpass_json([way]))] == [1]


def test_ways_are_yielded_before_the_remark_is_known():
    """The parser keeps streaming: the first way arrives while the rest of the
    response is unread."""
    body = _overpass_json([_way(i) for i in range(5000)], remark="runtime error: x")
    response = _FakeResponse(body)
    with mock.patch("cosmonaut_app.osm.source.requests.post", return_value=response):
        stream = OverpassSource("http://overpass.test").stream_ways(POLYGON, ["x"])
        first = next(stream)

    assert first["id"] == 0
    assert response.raw.tell() < len(body)


def test_a_truncated_response_raises_ijson_incomplete_json():
    body = _overpass_json([_way(1), _way(2)])

    with pytest.raises(ijson.IncompleteJSONError):
        _stream(body[: len(body) // 2])
