"""Every OpenStreetMap tile layer must send a Referer.

The UFZ cluster ingress answers every page with ``Referrer-Policy: same-origin``,
which strips the Referer from cross-origin requests, tile requests to
tile.openstreetmap.org included. OSM's tile usage policy requires a Referer, and
in October 2026 the deployed app served "Access blocked" tiles instead of a
map. The ``referrerPolicy`` option of the layer overrides the page policy per
tile.

A new OSM layer without it brings the outage back, and nothing else would notice:
the block only shows in a real browser against the real tile servers, never in a
suite. ``dl.TileLayer()`` without a ``url`` counts too, because dash-leaflet
defaults to the OSM tile server.

Read from the source: the layers sit in module-level layout code.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).parent.parent / "cosmonaut_app"

# Origin only: OSM gets a valid Referer, but no page path, which carries job ids.
REQUIRED_POLICY = "strict-origin-when-cross-origin"


def _is_osm_tile_layer(call):
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "TileLayer"):
        return False
    urls = [keyword.value for keyword in call.keywords if keyword.arg == "url"]
    if not urls:
        return True
    return (
        isinstance(urls[0], ast.Constant)
        and isinstance(urls[0].value, str)
        and "tile.openstreetmap.org" in urls[0].value
    )


def _referrer_policy(call):
    policies = [kw.value for kw in call.keywords if kw.arg == "referrerPolicy"]
    if policies and isinstance(policies[0], ast.Constant):
        return policies[0].value
    return None


def _osm_tile_layers():
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_osm_tile_layer(node):
                yield path.relative_to(APP_DIR.parent), node


def test_every_osm_tile_layer_sends_a_referer():
    missing = [
        f"{path}:{call.lineno}"
        for path, call in _osm_tile_layers()
        if _referrer_policy(call) != REQUIRED_POLICY
    ]

    assert not missing, (
        f'OSM tile layers without referrerPolicy="{REQUIRED_POLICY}":\n  '
        + "\n  ".join(missing)
    )


def test_the_scan_finds_the_osm_layer():
    """Guard the guard: a scan that finds nothing passes trivially."""
    assert list(_osm_tile_layers()), f"no OSM tile layer found under {APP_DIR}"
