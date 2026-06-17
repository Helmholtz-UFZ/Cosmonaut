# OSM backend

The `cosmonaut_app/osm/` package downloads the OpenStreetMap road network for a job's area and
writes the GeoJSON that sensor-routing consumes. It is a **direct Overpass** backend that replaced
an older osmnx-based downloader — same outputs, a fraction of the RAM (all of Saxony at ~152 MB peak
vs osmnx's ~12.5 GB). The *why* lives in the decision record
[20260605-osm-overpass-direct-vs-osmnx](../../decisions/20260605-osm-overpass-direct-vs-osmnx.md);
this page is the *how it works now*.

## The pipeline

[`OsmDownloader.run_osm_query(download_folder)`](../../../cosmonaut_app/osm/downloader.py) is the
entry point (called from [upload_tasks.py](../../../cosmonaut_app/tasks/upload_tasks.py) on the
worker). It streams one way at a time through four small modules:

```
OverpassSource.stream_ways()   →  raw OSM way (nodes + per-node geometry + tags)   source.py
        ↓
way_to_feature(way, polygon)   →  one GeoJSON LineString (EPSG:4326), or None       transform.py
        ↓
project_feature(feat, transf)  →  same feature reprojected to the job's EPSG        projection.py
        ↓
StreamingGeoJsonWriter.write() →  appended to disk incrementally + atomically       geojson_writer.py
```

The area queried is the **convex hull** of the membership points, buffered slightly
(`_get_convex_hull`). Only road `highway` types in `HIGHWAY_TYPES` are fetched (motorway … track) —
the same set the old osmnx `custom_filter` used.

## Three output files

Written into the job `working_dir`:

| File | CRS | Role |
|------|-----|------|
| `osm_data_download.geojson` | EPSG:4326 | Raw download, kept for reference |
| `osm_data_edited.geojson` | EPSG:4326 | Editable copy (starts identical to the download; the Street Selection page edits this) |
| `osm_data_transformed.geojson` (`OSM_FILENAME`) | job EPSG | The projected file **sensor-routing reads** |

The transformed file is regenerated from the edited file after every street-selection change — see
[sensor-routing-integration](sensor-routing-integration.md) and `street_selector.py`, which reproject
through the **shared** [projection.py](../../../cosmonaut_app/osm/projection.py) so the download path
and the edit path produce byte-identical output.

## Why it is memory-bounded

The old peak was `response.json()` materializing the entire parsed Overpass tree, not geopandas. So
the lever is **streaming the parse**:

- `OverpassSource.stream_ways` issues the `out geom` query with `requests(stream=True)` and walks the
  response with `ijson.items(response.raw, "elements.item")`, yielding ways one at a time. ijson emits
  numbers as `Decimal`; `way_to_feature` normalizes node ids to `int` and coordinates to `float`.
- `StreamingGeoJsonWriter` writes each feature straight to a `<path>.tmp` file and renames it into
  place (`os.replace`) only on a clean `__exit__`. A timeout mid-stream therefore **never leaves a
  half-written file** — the temp file is discarded. The projected writer emits a named-CRS header.

So at no point is the whole dataset (parsed response + all features + a GeoDataFrame) held in memory.

## Boundary fidelity

`_truncate_by_edge` in [transform.py](../../../cosmonaut_app/osm/transform.py) replicates osmnx's
`truncate_by_edge`: a node-pair survives if **either** endpoint is inside the polygon (so boundary
ways extend one node past the edge), trimming whole nodes only so the `nodes`↔`coords` alignment is
never broken. A way that leaves and re-enters the polygon fragments into multiple runs and is
**dropped** (osmnx would emit a MultiLineString there). `_infer_oneway` mirrors osmnx: explicit
one-way tags **or** roundabouts become `oneway: "yes"`.

## Swapping the source

`OverpassSource` defaults to the public endpoint but reads `OVERPASS_URL` from the environment:

```python
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
```

This is a **soft** env lookup (plain `os.getenv`, not the strict `config` loader) on purpose: it has
a working default, so it must not become a required variable enforced across all env files. Point it
at a self-hosted wiktorn instance or a UFZ endpoint for large areas. The `OsmSource` ABC keeps the
door open for a future `.osm.pbf` reader without touching the transform. **`TODO:` promote `OVERPASS_URL`
to a strict config var once the deployment Overpass source is chosen (project-state issue #36).**

## Gotchas

- The public endpoint answers **HTTP 406** to the default `python-requests` User-Agent — a descriptive
  `User-Agent` header is required (and is Overpass etiquette).
- `upload_tasks.py` retries 429/502/503/504 via `e.response is not None and …` — **not** `if e.response`,
  because `requests.Response.__bool__` returns `response.ok` (False for every status ≥ 400), which would
  silently never retry.

## Related links

- Code: [osm/downloader.py](../../../cosmonaut_app/osm/downloader.py),
  [osm/source.py](../../../cosmonaut_app/osm/source.py),
  [osm/transform.py](../../../cosmonaut_app/osm/transform.py),
  [osm/projection.py](../../../cosmonaut_app/osm/projection.py),
  [osm/geojson_writer.py](../../../cosmonaut_app/osm/geojson_writer.py)
- Decision: [20260605-osm-overpass-direct-vs-osmnx](../../decisions/20260605-osm-overpass-direct-vs-osmnx.md)
- Systems: [sensor-routing-integration](sensor-routing-integration.md) (consumes the transformed file),
  [background-tasks](background-tasks.md) (runs the download on the `upload` queue)
- Concept: [cosmonaut-job](../concepts/cosmonaut-job.md) (owns the `working_dir` these files live in)
- Current state: [project-state.md](../../project-state.md)
