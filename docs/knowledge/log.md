# Knowledge Log

Most recent first. One dated entry per change set; list the pages added or substantially revised.

## 2026-06-24

- Added `runbooks/local-overpass-testing.md` — standing up a local self-hosted Overpass
  (merged Sachsen + Sachsen-Anhalt + Brandenburg on the mirrored image) and pointing
  COSMONAUT at it via `OVERPASS_URL`; validated route-equivalent to public on a sampled AOI.
- Revised `systems/osm-backend.md` — the self-hosted source path is now demonstrated
  end-to-end; added the full-interpreter-URL and cross-repo `DIFF_URL :-` gotchas.

## 2026-06-17

- Added `concepts/cosmonaut-job.md` — the `CosmonautJob` state object and its two-tier persistence.
- Added `systems/osm-backend.md` — the Overpass-direct OSM road-network downloader.
- Added `systems/sensor-routing-integration.md` — integration with the external routing engine.
- Added `systems/background-tasks.md` — the Celery queue architecture and status-sync flow.
- Seeded the knowledge base skeleton (`index.md`, `log.md`, `concepts/ systems/ datasets/ runbooks/ raw/`).
