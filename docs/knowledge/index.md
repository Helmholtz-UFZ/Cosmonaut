# Knowledge Base

Durable, cross-linked explanations of the concepts, subsystems, and data that an agent or
newcomer repeatedly needs to work on COSMONAUT correctly. This is **not** the place for
coding rules ([conventions/](../conventions/)), one-off decisions
([decisions/](../decisions/)), or transient plans (`docs/plan/`).

See [log.md](log.md) for the change history. New pages must be added to this index and
should link to at least one related page.

## Concepts

Durable ideas used across the codebase.

- [cosmonaut-job](concepts/cosmonaut-job.md) — The `CosmonautJob` state object: the two-tier
  persistence model (Postgres JSONB + MinIO), `stage`/`status`/`street_processing` semantics,
  and the `sync_files`/`overwrite` web-pod-vs-worker-pod rules.

## Systems

Major subsystems and how they interact.

- [osm-backend](systems/osm-backend.md) — The `cosmonaut_app/osm/` Overpass-direct road-network
  downloader: streaming parse, atomic GeoJSON writer, why it replaced osmnx.
- [sensor-routing-integration](systems/sensor-routing-integration.md) — How COSMONAUT drives the
  external `sensor-routing` engine, the file contract, and the O(n²) / globally-coupled constraint.
- [background-tasks](systems/background-tasks.md) — The Celery queue architecture and the
  web→MinIO→worker→status-sync flow.

## Datasets

Input/reference data and schemas. _(none yet — see [datasets/](datasets/))_

## Runbooks

Operational guides for recurring tasks. _(none yet — see [runbooks/](runbooks/))_

## Raw

Curated source material that feeds pages. _(none yet — see [raw/](raw/))_
