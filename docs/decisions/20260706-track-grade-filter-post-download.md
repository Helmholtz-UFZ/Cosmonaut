# 20260706 — Track-grade filter is post-download, not query-time

**Date:** 2026-07-06
**Status:** accepted

**Context:** Supervisor request: expose OSM `tracktype` grades 1–5 in the road
network specification, with grades 1–3 accepted by default (field practice —
grade 4/5 tracks are mostly soft-surfaced and rarely traversable by survey
vehicles; `tracktype` mapping quality in OSM is inconsistent). Two possible
homes existed:

- **(A) Post-download filter** in `StreetSelector` (like the existing highway
  type checklist): filter `osm_data_edited.geojson` from the immutable
  `osm_data_download.geojson`, persist in `street_edits.json`.
- **(B) Query-time filter** in the Overpass query (`osm/source.py`): split the
  single highway regex clause into a union query with a separate
  `["tracktype"~...]` clause, persist on the Pydantic `JobModel`, thread
  through `submit_upload_job` → `process_upload_task` → `OsmDownloader`.

**Decision:** (A) — post-download. `tracktype` is already fetched into every
feature's properties (`osm/transform.py` `PROPERTY_ORDER`), so the data is
free. Grade changes on the Street Selection page are instant and reversible
(no re-download), matching the "download once immutably, filter forever"
architecture from
[20260605-osm-overpass-direct-vs-osmnx](20260605-osm-overpass-direct-vs-osmnx.md).

Two supporting details:

- **The default is applied at download time** in `OsmDownloader.run_osm_query`
  (streaming, per-way predicate `road_network_utils.track_grade_allowed`) when deriving the
  initial `osm_data_edited.geojson`/`osm_data_transformed.geojson` — otherwise
  the UI would show grades 4–5 disabled while the network still contained
  them until the first manual edit. The download file itself stays unfiltered.
  The shared default lives in `constants/general.py::DEFAULT_TRACK_GRADES`.
- **Tracks without a `tracktype` tag** (common in OSM) form an explicit
  "No grade tag" bucket in the checklist and are **excluded by default**
  (user decision 2026-07-07): their condition is unknown, and field practice
  only accepts known-good grades 1–3. They can be re-enabled with one click.
  Non-standard tag values are treated as untagged. (This bullet was revised
  twice on 2026-07-07 — first the bucket was default-included, then briefly
  removed as "redundant with the Track toggle", finally restored with
  default-excluded semantics because untagged tracks are too numerous to
  include blindly.)

**Consequences:**

- No Overpass query change; download volume is unchanged (grade 4/5 tracks are
  still fetched, just filtered out of the working network).
- Legacy `street_edits.json` files (pre-feature) are migrated on load to
  "all grades" so in-flight jobs keep their network unchanged; only new
  downloads and explicit resets get the 1–3+ungraded default.
- If Saxony-scale download volume ever becomes a problem, (B) can still be
  added on top as an optimization — the `street_edits.json` state model would
  not change.
