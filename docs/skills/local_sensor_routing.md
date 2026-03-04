# Skill: Local sensor-routing development

Use this skill when the user asks you to make changes to the `sensor-routing` library
in the context of COSMONAUT integration work. This covers editing files across both
repositories.

---

## Step 1 — Locate the sensor-routing repo

Parse `docker-compose.local-sr.yml` in the COSMONAUT project root. Extract the host
path from the volume mount (the part before the `:`). It is relative to the COSMONAUT
project root.

```yaml
# Example: the volume line looks like this
volumes:
  - "../sensor-routing:/python_docker/sensor-routing"
#    ^^^^^^^^^^^^^^^^^^  ← this is the relative path
```

Resolve it to an absolute path relative to the COSMONAUT project root.

## Step 2 — Verify the repo exists

Check that the resolved path is a directory **and** a git repository (contains `.git`).
If it does not exist, stop and tell the user:

> sensor-routing repo not found at `<resolved path>`.
> Clone it there or update the volume mount in `docker-compose.local-sr.yml`.

Do not create the directory or clone anything without explicit user instruction.

## Step 3 — Understand the integration boundary

sensor-routing is an **external library** with its own maintainer. COSMONAUT depends on
it via PyPI (`pyproject.toml` pins a version). The `--local-sr` flag is available in
both `dev_up.sh` and `run_pytest.sh`:

- **`dev_up.sh --local-sr`** — volume-mounts the local repo into the container and
  prepends it to `PYTHONPATH`, shadowing the PyPI version.
- **`run_pytest.sh --local-sr`** — prepends the local repo to `PYTHONPATH` before
  running `uv run pytest`, so tests use the local sensor-routing on the host.

Key files at the boundary:

| COSMONAUT side | sensor-routing side |
|---|---|
| `cosmonaut_app/pydantic_models.py` — imports `FullPipelineConfig` | `sensor_routing/full_pipeline_cli.py` — defines `FullPipelineConfig` |
| `cosmonaut_app/tasks/routing_tasks.py` — calls `sensor_routing_pipeline()` | `sensor_routing/full_pipeline_cli.py` — defines `sensor_routing_pipeline()` |
| `cosmonaut_app/constants/general.py` — imports filename constants | `sensor_routing/full_pipeline_cli.py` — defines `PREDICTOR_FILENAME` etc. |

When making changes, think about which side of the boundary owns the thing you are
changing. Prefer changing sensor-routing to expose a clean API rather than working
around its internals in COSMONAUT.

## Step 4 — Understand the three pipeline input files

`sensor_routing_pipeline(work_dir)` expects exactly three files in the working
directory before it runs. COSMONAUT is responsible for producing all three during the
data-upload / street-selection workflow.

### File 1 — `memberships.csv` (`MEMBERSHIP_FILENAME`)

**Produced by:** `CosmonautJob.upload_membership()` in `cosmonaut_app/cosmonaut_job.py`.
The user uploads a CSV on the Data Upload page; it is saved verbatim under the
canonical name and validated with `parse_membership_file()` from sensor-routing.

**Format (from `DESCRIPTION_MEMBERSHIP` in sensor-routing):**

```
Easting,Northing,Cluster1,Cluster2,...
423150.5,5418230.2,0.7,0.2,0.1
423155.5,5418230.2,0.1,0.8,0.1
```

- Header row required.
- First two columns: Easting, Northing in the job's projected EPSG (not 4326).
- Remaining columns: fuzzy cluster membership probabilities (each row sums to ~1.0).
- Must be consistent with `predictors.csv` (same points, same order).

### File 2 — `predictors.csv` (`PREDICTOR_FILENAME`)

**Produced by:** `CosmonautJob.upload_predictor()`. The user uploads a CSV on the
Data Upload page; it is saved and cross-validated against the membership file with
`validate_predictor_membership_consistency()`.

**Format (from `DESCRIPTION_PREDICTOR` in sensor-routing):**

```
Easting,Northing,Mask,DEM,Slope,SOC,Clay,...
619500.0,5786500.0,0.0,132.95,5.2,1.8,0.25
```

- Header optional (auto-detected).
- Column 1: Easting, Column 2: Northing — same CRS and same points as membership file.
- Column 3: Urban mask (0 = rural, 1 = urban).
- Columns 4+: environmental predictor variables (arbitrary number and names).
- NaN values allowed in predictor columns.

### File 3 — `osm_data_transformed.geojson` (`OSM_FILENAME`)

**Produced by:** `OsmDownloader.run_osm_query()` (called during membership upload) and
then **regenerated** by `StreetSelector.save()` after every street-selection change.
The file is the projected version of the edited road network; the user never uploads it.

**Key properties required by sensor-routing** (`point_mapping.py`):

| Property | Type | Description |
|---|---|---|
| `osmid` | integer | OSM way ID — used as the road identifier throughout the pipeline |
| `nodes` | list of integers | Ordered OSM node sequence for the way |
| `highway` | string | OSM highway tag value |
| `oneway` | `"yes"` / `"no"` | Normalised by `OsmDownloader._normalize_for_routing()` |

**CRS:** projected to the job's EPSG code (same CRS as the CSV files), **not** 4326.
The 4326 source lives in `osm_data_download.geojson` / `osm_data_edited.geojson`;
`osm_data_transformed.geojson` is the reprojected export that sensor-routing reads.

**Common pitfall:** `osmid` must be present in `properties`, not just as the top-level
GeoJSON feature `id`. If `osmid` is missing from `OsmDownloader.columns_to_keep` it
is silently dropped before the file is written, causing a `KeyError: 'osmid'` deep
inside `point_mapping.build_node_to_roads_map()`.

## Step 5 — Make changes

Edit files in both repos as needed. Follow the conventions of each project:

- **COSMONAUT**: follow `CLAUDE.md` and the conventions in `docs/conventions/`.
- **sensor-routing**: this repo has no `CLAUDE.md`. It uses a different code style
  (less strict formatting, `print()` for debug output, etc.). Match the existing style
  of the file you are editing — do not impose COSMONAUT conventions on sensor-routing.

## Step 5 — Run the sensor-routing tests

After making changes, run the sensor-routing test suite to verify nothing is broken.
The dependencies must be installed first (the pyenv for sensor-routing is already set up
on this machine):

```bash
pip install -e ".[dev]"   # only needed once, or after dependency changes
pytest test/ -v
```

There is currently one integration test (`test/test_full_procedure.py`) that runs the
full pipeline against test data in `sensor_routing/test_data/`. It takes ~1 minute.

## Step 6 — Git: always ask

The two repos have **separate git histories**. sensor-routing has no formalized branching
or release workflow — the maintainer publishes to PyPI by hand.

**Always ask the user how to proceed with git operations.** Do not assume a branching
strategy, do not create branches or commits without explicit instruction. Reasonable
questions to ask:

- "Should I commit these sensor-routing changes? On which branch?"
- "Should I commit the COSMONAUT changes separately?"
- "Do you want to handle the sensor-routing push/publish yourself?"
