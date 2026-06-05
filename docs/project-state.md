# Project State

Read at the start of every session (see CLAUDE.md § Session Continuity). Update at the end of sessions that involved significant decisions or new patterns.

## Current priorities

_(What's actively being worked on. Short bullets, replace as work shifts.)_

- **Large-area (Saxony) scaling — OSM download SOLVED via Overpass-direct.** Replaced the osmnx graph build with a direct Overpass `out geom` query (new package `cosmonaut_app/osm/`). Proven **route-equivalent** to osmnx and **3.2 GB peak for all of Saxony** (vs osmnx 12.5 GB) — under the 7 GB cluster limit. **No longer blocked on WKDV**: we self-host wiktorn or read a `.pbf`; WKDV's answer only optimizes the *source*. **Open: production swap of `upload_tasks.py` + choose the deployment Overpass source.** Decision record: [decisions/20260605-osm-overpass-direct-vs-osmnx.md](decisions/20260605-osm-overpass-direct-vs-osmnx.md). GitLab issue #36. Branch: `36-osm-saxony-is-to-big`. (Routing-scale — sensor-routing O(n²), not tileable per Can — remains a separate question; see Open questions.)
- Cleanup passes on user-facing pages to improve clarity before the sensor-routing backend rework (Can, earliest May 2026).

## Recent changes

_(Most recent first. Trim older entries when they stop being load-bearing.)_

- **2026-06-05 (implementation)** — Built the Overpass-direct OSM backend (`cosmonaut_app/osm/`: `source.py` + `transform.py` + `downloader.py`), resolving the scaling block from the investigation entry below. Key points:
  - **Why it works:** the 12.5 GB was the osmnx networkx graph, which the old pipeline then *un-builds* (`_reconstruct_ways`) back into the OSM way node sequences that Overpass `out geom` returns natively. Direct query → no graph → RAM scales with the road data, not a graph.
  - **Fidelity proven** (`test/fixtures/compare_osm_backends.py`, both backends vs the same Overpass, osmnx cache off): test AOI route-equivalent (0 roads lost, 0 node-set/tag mismatches, **0 m** geom delta, sensor-routing connectivity map identical). Two understood deltas: roundabout start-node rotation (neutral; oneway now inferred osmnx-style) and one track osmnx *drops* (MultiLineString artifact) which the new backend keeps — measured **routing-redundant** (covers 2 points, both already covered; reachable coverage 483 = 483).
  - **Saxony RAM:** 3.2 GB / 77 s / 375k features / 357 MB against self-hosted wiktorn (vs osmnx 12.5 GB). Output matches Can's faithful Saxony network.
  - **Gotchas:** osmnx caches Overpass responses (`use_cache=False` for honest comparison); overpass-api.de 406s the default python-requests User-Agent.
  - **Artifacts:** `cosmonaut_app/osm/` (new backend, old `osm_downloader.py` kept as reference), `test/test_osm_transform.py` (6 offline contract tests, green), `test/fixtures/overpass_test_aoi.json` (committed fixture), `test/fixtures/compare_osm_backends.py` (spike, `--new-only` for Saxony). `requests` added as explicit dep. Decision: [decisions/20260605-osm-overpass-direct-vs-osmnx.md](decisions/20260605-osm-overpass-direct-vs-osmnx.md).
  - **Next:** swap `upload_tasks.py` import (`cosmonaut_app.osm_downloader` → `cosmonaut_app.osm`), then remove old module; pick deployment Overpass source (wiktorn vs `.pbf`) and promote `OVERPASS_URL` to a strict config var.
- **2026-06-05 (investigation)** — Investigated large-area (Saxony) scaling (GitLab issue #36; branch `36-osm-saxony-is-to-big`). What we know:
  - **OSM build:** the app's `OsmDownloader` (osmnx graph over the convex hull) for all of Saxony **completes but needs ~12.5 GB RAM** (peak 12.1 GB; OOMs below that). Cost scales with hull **area**, not membership-grid density. Cluster worker is limited to 7 GB.
  - **Overpass:** public Overpass rate-limits/blocks Saxony-sized queries. Self-hosted **`wiktorn/overpass-api`** (Geofabrik Saxony extract) works and is **byte-faithful** with osmnx via a one-line `osmnx.settings.overpass_url` change. (`kartoza/docker-osm` rejected: it's PostGIS, osmnx can't query it → would need a road-fetch rewrite + lose fidelity.)
  - **Routing:** `sensor-routing` (all-pairs shortest paths + Ant Colony Optimization over global matrices, O(n²)) is **globally coupled** — a single route can't be tiled/stitched; "many survey-sized jobs" is the path. **Can** (sensor-routing dev) has the Saxony road network and will measure routing RAM/CPU/time at full-Saxony scale.
  - **Direction:** wiktorn (local OSM source, solves Overpass fragility) **+ tiling** (many small jobs, solves scale). Both halves demonstrated individually. Not yet integrated — **waiting on WKDV** before touching the deployment.
  - **Resume steps (after WKDV answers):** (1) if UFZ has an Overpass API → point `osmnx.settings.overpass_url` at it (make env-configurable), no self-hosting; (2) if UFZ has OSM data only → load it into a wiktorn container; (3) if neither → deploy our own wiktorn (Germany Geofabrik extract) as a cosmonaut service. Then in all cases: make `overpass_url` env-configurable, add the overpass service to deployment, scaffold `osm/` in the branch. Open product question for Can: continuous route vs. per-region (tiled) routes.
  - **Local artifacts (scratch, outside repo):** wiktorn at `~/git/cache/wiktorn-overpass/` (Saxony loaded; `docker compose up -d` serves on :12345, instant — init already done). Faithful Saxony road network delivered to Can: `~/git/cache/sachsen/saxony_road_network_EPSG25832.geojson` (+ `.README.txt`).
- **2026-04-22** — Street Selection page restructured into zone-based layout (filter → per-item edit → algorithmic → footer-level undo). New convention: [conventions/page_zones.md](conventions/page_zones.md).
- **2026-04-22** — Routing Parameters page split into essential + advanced tiers with `dbc.Collapse`. New convention: [conventions/form_partition.md](conventions/form_partition.md).

## Open questions

- `optimization_objective` is still a free-text input accepting `d`/`t`/`i`. Can's backend rework (earliest May 2026) is expected to clarify semantics — revisit UX then (radio/dropdown, active/inactive indicators on Time Limit / Max distance).
- `Reset all edits` on Street Selection resets per-edit state only. Unclear whether a separate "reset job to factory state" action is needed — currently that's covered by the job reset banner/modal for non-PENDING jobs.
