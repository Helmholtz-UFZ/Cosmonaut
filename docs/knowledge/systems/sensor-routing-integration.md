# sensor-routing integration

The actual route optimization is **not** in this repo. COSMONAUT is a workflow + persistence shell
around `sensor-routing`, an external library with its own maintainer (Can), pinned by version in
[pyproject.toml](../../../pyproject.toml) (`sensor-routing==0.2.6`). This page covers the integration
boundary and the one performance fact that shapes the whole product's scaling strategy.

For cross-repo *editing* of sensor-routing (local checkout, running its tests, git etiquette) and the
exact **input-file formats**, follow the skill
[local_sensor_routing](../../skills/local_sensor_routing.md) — this page does not duplicate those.

## What COSMONAUT calls

The boundary is deliberately small. Everything goes through `sensor_routing.full_pipeline_cli`:

| COSMONAUT side | Uses from sensor-routing |
|----------------|--------------------------|
| [pydantic_models.py](../../../cosmonaut_app/pydantic_models.py) | `FullPipelineConfig` — subclassed by `UserModel`/`JobModel`; its fields become the job's JSONB `config` |
| [tasks/routing_tasks.py](../../../cosmonaut_app/tasks/routing_tasks.py) | `sensor_routing_pipeline(work_dir)` — the one call that runs the whole optimization |
| [cosmonaut_job.py](../../../cosmonaut_app/cosmonaut_job.py) | `parse_membership_file`, `parse_predictor_file`, `validate_predictor_membership_consistency` (upload validation) |
| [constants/general.py](../../../cosmonaut_app/constants/general.py) (and others) | `MEMBERSHIP_FILENAME`, `PREDICTOR_FILENAME`, `OSM_FILENAME`, `ROUTE_FILENAME` |

## The file contract

`sensor_routing_pipeline(work_dir)` is filesystem-driven: it reads **three input files** from the
working directory and writes a route solution back. COSMONAUT's whole job is to produce those three
files, under their canonical names, before calling it:

- `memberships.csv` (`MEMBERSHIP_FILENAME`) — produced by `CosmonautJob.upload_membership()`.
- `predictors.csv` (`PREDICTOR_FILENAME`) — produced by `CosmonautJob.upload_predictor()`.
- `osm_data_transformed.geojson` (`OSM_FILENAME`) — produced by the [osm-backend](osm-backend.md) and
  regenerated after street-selection edits.

`CosmonautJob.dump_routing_params()` additionally writes `parameters.json` (the `FullPipelineConfig`
fields) into the working dir. Full column-level formats are in
[local_sensor_routing](../../skills/local_sensor_routing.md) (§Step 4).

## The run path

In `process_routing_job` on the worker:

```python
StreetSelector(job).ensure_projected()        # guarantee osm_data_transformed.geojson is current
sensor_routing_pipeline(job.working_dir)       # the optimization
job.create_qr_code_routing()                   # post-process: route.gpx + QR from the solution
```

The result is `ROUTE_FILENAME` in the working dir; `CosmonautJob.get_route_polyline()` reads its
`Path` and reprojects to WGS84 for the map. Logging is switched to a per-job file in `working_dir`
for the duration of the run, then switched back.

## The constraint that drives everything: O(n²), globally coupled

sensor-routing computes **all-pairs shortest paths + Ant Colony Optimization over global matrices**.
That makes it **O(n²) and globally coupled**: a single route cannot be split into tiles and stitched
back together, because every point's cost depends on every other point. This is *the* reason
large-area scaling is approached as **many survey-sized jobs** rather than one big tiled job — see
[project-state.md](../../project-state.md). (Note this is separate from the OSM *download* scaling,
which the [osm-backend](osm-backend.md) already solved.) **`TODO:` Can to measure routing RAM/CPU/time
at full-Saxony scale — those numbers are not yet known.**

## Do / Don't

- **Do** route changes through the boundary table above; prefer asking sensor-routing to expose a clean
  API over reaching into its internals from COSMONAUT.
- **Do** match sensor-routing's own (looser) code style when editing that repo — do not impose COSMONAUT
  conventions on it (see the skill).
- **Don't** assume routing is tileable. It is not.
- **Don't** rename or relocate the three input files — `sensor_routing_pipeline` finds them by canonical
  name in `work_dir`.

## Related links

- Skill: [local_sensor_routing](../../skills/local_sensor_routing.md) — cross-repo editing + file formats
- Code: [routing_tasks.py](../../../cosmonaut_app/tasks/routing_tasks.py),
  [pydantic_models.py](../../../cosmonaut_app/pydantic_models.py),
  [street_selector.py](../../../cosmonaut_app/street_selector.py)
- Systems: [osm-backend](osm-backend.md) (produces the GeoJSON input),
  [background-tasks](background-tasks.md) (runs the pipeline on the `routing` queue)
- Concept: [cosmonaut-job](../concepts/cosmonaut-job.md) (`config` JSONB = `FullPipelineConfig` fields)
- Current state: [project-state.md](../../project-state.md)
