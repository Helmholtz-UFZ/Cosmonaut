# Decision: Replace osmnx with a Direct Overpass Query for OSM Road Download

**Date:** 2026-06-05
**Status:** Accepted (download approach); production swap of `upload_tasks.py` pending
**Context:** GitLab issue #36 — large-area (Saxony) scaling. The app's OSM road
download (`cosmonaut_app/osm_downloader.py`) builds an osmnx networkx graph over the
convex hull of the survey points. For all of Saxony this needs **~12.5 GB peak RAM**
(OOMs below ~12.1 GB), while the cluster worker is capped at **7 GB**. The work was
previously blocked waiting on a WKDV ticket (does UFZ provide an Overpass API / OSM
data). See `docs/project-state.md`.

## Decision

Fetch OSM road data **directly from an Overpass API** (`way["highway"~...](poly:);
out geom;`) and build the routing GeoJSON straight from the returned ways, instead of
building (and immediately un-building) an osmnx graph.

New package `cosmonaut_app/osm/`:

- `source.py` — `OverpassSource` (HTTP `out geom`), behind an `OsmSource` interface so
  the backend is swappable (self-hosted Overpass now, a local `.osm.pbf` reader later).
  Endpoint is env-configurable via `OVERPASS_URL` (soft default = public Overpass).
- `transform.py` — raw ways → GeoJSON features. Replicates osmnx `truncate_by_edge`
  and osmnx oneway inference; no networkx graph.
- `downloader.py` — drop-in `OsmDownloader` (same constructor + `run_osm_query`, same
  three output files, `epsg_output` parametrized).

The old `osm_downloader.py` is kept as a reference until the production swap lands.
This decision unblocks #36 **without** the WKDV ticket: we self-host Overpass (wiktorn)
or read a `.pbf`; WKDV's answer only optimizes the *source*, it no longer blocks.

## Rationale

- **The 12.5 GB is the graph, not Overpass.** `osmnx.graph_from_polygon` builds a full
  networkx `MultiDiGraph` (every OSM node → graph node, every node-pair → 2 edges).
  Swapping the Overpass source (the previously-validated wiktorn path) fixes
  rate-limiting but **not** the RAM. The graph is the root cause.
- **The pipeline builds the graph only to un-build it.** `_reconstruct_ways` /
  `_chain_edges` re-chain osmnx's per-node-pair edges back into the original OSM way's
  node sequence — i.e. exactly what Overpass `out geom` returns natively (parallel
  `nodes` + `geometry` arrays). ~250 lines of round-trip removed.
- **`nodes` is the whole contract.** sensor-routing rebuilds its routing graph purely
  from shared OSM node ids (`point_mapping.build_node_to_roads_map`). Overpass preserves
  node ids natively; this is also why a PostGIS source (kartoza/docker-osm) is rejected —
  its rendering schema does not carry the per-way node-id list.

## Evidence

Apples-to-apples comparison (`test/fixtures/compare_osm_backends.py`), both backends
against the **same** Overpass endpoint (osmnx cache disabled):

- **Route-equivalent on the test AOI:** 0 roads only-in-old, 0 node-set mismatches,
  0 routing-tag mismatches, **max geometry delta 0 m**, sensor-routing connectivity map
  byte-identical on shared roads.
- **Saxony RAM:** osmnx **12.5 GB** → Overpass-direct (geopandas) **3.2 GB** →
  **streaming 152 MB** (54 s, 375,293 features). The streaming path parses the response
  incrementally (ijson) and writes features one at a time, so the peak is ~one way, not
  the whole dataset. Streaming output is bit-identical to the geopandas path (0.0 m
  projection delta) and the ijson parse is byte-identical to the json parse.
- **Track-impact measured:** the one differing way (track 771997790) is *routing-
  redundant* — it covers 2 survey points, both already covered by roads present in both
  backends; total reachable coverage identical (483 = 483). Including it cannot reduce
  route quality.

## Fidelity decisions (where new ≠ osmnx, and why it's fine)

- **Boundary (`truncate_by_edge`)** is replicated at node granularity: keep each node-pair
  with ≥1 endpoint inside the hull; trims boundary ways to +1 node, never splits a
  segment (so `nodes`↔coords alignment is preserved). Ways that fragment into a
  MultiLineString are dropped — matching the old pipeline.
- **oneway is inferred osmnx-style** (`osmnx.graph._is_path_one_way` rules 3+4): `yes`
  if explicitly tagged one-way OR `junction=roundabout`, else `no`. Reproduces osmnx's
  roundabout inference (OSM doesn't tag those one-way) so `is_oneway` matches exactly.
- **osmnx's MultiLineString drop is NOT replicated.** osmnx silently drops valid ways
  whose graph edges don't rechain into a single line; the new backend keeps the original
  OSM way. Replicating the drop would require reintroducing osmnx's graph logic, and the
  measured impact is nil (redundant coverage). New is strictly more OSM-faithful here.

## Known Limitations

- **Closed-way (roundabout) start-node rotation:** same node *set*, different start node
  than osmnx. Routing-neutral (connectivity map keyed on node sets is identical). For a
  roundabout that *carries* survey points, `is_road_isolated` (which checks only the
  start/end node of a closed way) could flip — but this fragility is inherent to osmnx's
  output too, not introduced here.
- **`oneway=-1`:** osmnx additionally reverses geometry direction; the new backend keeps
  OSM order (is_oneway parity holds). None present in the test AOI; rare in practice.
- **Routing scale is separate.** A full-Saxony download is 375k roads; sensor-routing is
  globally O(n²) and (per Can) not tileable, so the whole network can't go into one
  routing job. That "many survey-sized jobs" question is unchanged by this decision.

## Gotchas discovered

- **osmnx caches Overpass responses** (`./cache`, `use_cache=True`). Comparisons must set
  `use_cache=False` or osmnx silently serves stale data (it cost us a false "extra way").
- **overpass-api.de answers 406** to the default `python-requests` User-Agent; a
  descriptive UA is required (and is good Overpass etiquette).

## Verification

- `./run_pytest.sh --no-services test/test_osm_transform.py` — 6 offline contract tests pass.
- `test/fixtures/compare_osm_backends.py` — VERDICT: ROUTE-EQUIVALENT on the test AOI.
- Saxony RAM measured against self-hosted wiktorn (Saxony extract) on :12345.

## Follow-ups

- ~~Swap `cosmonaut_app/tasks/upload_tasks.py` to `cosmonaut_app.osm`; then remove the
  old module.~~ **Done** — `upload_tasks.py` swapped, `cosmonaut_app/osm_downloader.py`
  **deleted**, `osmnx` removed from cosmonaut's direct deps, and
  `compare_osm_backends.py` reworked (measurement + optional `--reference` file diff,
  no osmnx baseline). **Caveat: osmnx is still installed transitively** — it's a
  dependency of `sensor-routing==0.2.6`, so the image/CI does not get lighter until
  sensor-routing drops it (raise with Can; sensor-routing may not actually use it).
- Decide the production Overpass source (self-hosted wiktorn vs `.pbf` reader) and add it
  to the deployment; promote `OVERPASS_URL` to a strict config var at that point.
- ~~Optional: stream the Overpass response / write GeoJSON incrementally to push the
  3.2 GB peak lower.~~ **Done** — `OverpassSource.stream_ways` (ijson) +
  `StreamingGeoJsonWriter` + per-way pyproj projection bring Saxony to 152 MB. Also
  vectorized truncate-by-edge (`shapely.contains_xy` on a prepared polygon, 3.1× faster,
  no RAM cost).
- ~~Migrate `street_selector.py` off the old `osm_downloader.project_and_save` (geopandas)
  to the new package's projection.~~ **Done** — `osm/projection.py` (`project_feature` +
  `project_features_to_file`) is now shared by the download and edit paths (output
  byte-identical, 0 m delta). The old `osm_downloader.py` has no production importers
  left; it stays only as the osmnx baseline in `compare_osm_backends.py`.
