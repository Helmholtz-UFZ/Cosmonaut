# Architecture

Package structure and pipeline overview for COSMONAUT. For the *why* behind specific
patterns see [conventions/](conventions/); for past design choices see
[decisions/](decisions/); for what's being worked on now see [project-state.md](project-state.md).

## What it is

COSMONAUT optimizes navigation routes for mobile Cosmic Ray Neutron Sensor (CRNS) rover
surveys. It turns membership-classification data into field-ready GPS routes through a
guided, multi-page workflow whose state is persisted so users can pause and resume.

## Service topology

A Dash web app backed by Celery workers and three datastores:

| Service | Role |
|---------|------|
| **cosmonaut-web** (Dash 3.x / Gunicorn) | Reactive Python UI, multi-page app (`use_pages=True`) |
| **cosmonaut-worker** (Celery 5.x) | Background, resource-intensive jobs (OSM download, route computation) |
| **PostgreSQL 15** | Main storage — `jobs` table (metadata, status enum, EPSG, JSONB `config`) + all service logs |
| **Redis 7** | Celery broker + result backend |
| **MinIO** (S3-compatible) | Durable per-job working dirs (`cosmonaut-jobs/{job_id}/`), keeps web containers stateless |
| **tileserver** | Map tiles (production) |

The web container is stateless: each job's `work_dir` syncs to MinIO via rclone, so
containers can restart without data loss. Local dev brings everything up with
`./dev_up.sh mock`; production runs on Kubernetes with managed Postgres/MinIO.

## The workflow (pages)

Seven guided steps plus admin/utility pages. Pages live in
[cosmonaut_app/pages/](../cosmonaut_app/pages/) and self-register via Dash
`register_page()`; per-job pages carry the `job_id` in the path.

| Step | Path | Page |
|------|------|------|
| 1 | `/` | Home — start / resume a job |
| 2 | `/job/<job_id>/user-info` | User Information |
| 3 | `/job/<job_id>/data-upload` | Data Upload (membership data → OSM road network) |
| 4 | `/job/<job_id>/street-selection` | Street Selection (filter / edit / undo) |
| 5 | `/job/<job_id>/routing-params` | Routing Parameters (essential + advanced tiers) |
| 6 | `/job/<job_id>/route-computation` | Route Computation (runs sensor-routing) |
| 7 | `/job/<job_id>/route-download` | Route Download (GPX + QR/email) |

Utility pages (not part of the linear flow): `/job-manager`, `/worker-management`,
`/logs`, `/documentation`.

## Background pipeline (Celery)

Tasks live in [cosmonaut_app/tasks/](../cosmonaut_app/tasks/) and are routed to queues
by [celery_config.py](../cosmonaut_app/celery_config.py):

| Module | Queue | Does |
|--------|-------|------|
| `upload_tasks.py` | `upload` | `process_upload_task` — download + project the OSM road network for the job's area |
| `routing_tasks.py` | `routing` | `process_routing_job` — run sensor-routing, notify the user on completion |
| `maintenance_tasks.py` | (default) | `cleanup_task` / `clean_up_jobs` — periodic cleanup of stale jobs |

Routing itself is delegated to the external **`sensor-routing`** library (all-pairs
shortest paths + Ant Colony Optimization over global matrices — O(n²), globally coupled,
*not* tileable; see [project-state.md](project-state.md)).

## Package map

[cosmonaut_app/](../cosmonaut_app/) — application package:

| Path | Responsibility |
|------|----------------|
| `app.py` | Dash app construction + `use_pages` bootstrap |
| `celery_app.py`, `celery_config.py` | Celery app + queue routing |
| `pages/` | One module per workflow/utility page (self-registering) |
| `tasks/` | Celery tasks (upload, routing, maintenance) |
| `components/` | Reusable layout components |
| `constants/` | `html_ids.py` (centralized HTML IDs — never literals) + `general.py` |
| `osm/` | Overpass-direct OSM backend: `source.py` (stream), `transform.py`, `downloader.py`, `projection.py`, `geojson_writer.py` (atomic GeoJSON) |
| `pydantic_models.py` | Routing config models (serialized to the `jobs.config` JSONB) |
| `cosmonaut_job.py` | `CosmonautJob` — job state object |
| `db_manager.py` | PostgreSQL access (jobs + logs) |
| `object_storage_manager.py` | MinIO sync of per-job working dirs |
| `error_handling.py` | Custom exceptions + error modal (see [conventions/error_handling.md](conventions/error_handling.md)) |
| `logger.py`, `logs_table.py` | DB-backed logging (see [conventions/logging.md](conventions/logging.md)) |
| `navigation_routing.py`, `road_network_utils.py`, `street_selector.py` | Road-network handling + street editing |
| `map_utils.py`, `classification_plot.py` | Map + plot rendering |
| `email_service.py` | User/maintainer notifications |
| `doc_generator.py`, `doc_pages_config.py`, `screenshot_generator.py` | In-app documentation page generation |

## Key external dependencies

Dash 3.x + dash-bootstrap-components + dash-leaflet + dash-extensions (UI/maps);
Celery[redis] (queue); SQLAlchemy + psycopg2 (Postgres); minio (object storage);
pydantic v2 (config models); geopandas / shapely / pyproj / rasterio / GDAL (geospatial);
ijson + requests (streaming Overpass); **sensor-routing** (the routing engine).

## Where the OSM backend stands

The `osm/` package is a direct Overpass `out geom` backend that replaced the old osmnx
graph build — same routes, far less RAM (all of Saxony at ~152 MB peak vs osmnx's
12.5 GB). Rationale and current open items (production swap, deployment Overpass source)
are in [decisions/20260605-osm-overpass-direct-vs-osmnx.md](decisions/20260605-osm-overpass-direct-vs-osmnx.md)
and [project-state.md](project-state.md).
