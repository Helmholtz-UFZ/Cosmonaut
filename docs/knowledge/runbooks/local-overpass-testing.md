# Runbook: Test COSMONAUT against a local self-hosted Overpass

Point COSMONAUT's OSM road download at a **local** Overpass instead of public
overpass-api.de — so large multi-region AOIs (which public rate-limits/blocks) fetch
locally and deterministically. Mirrors the production setup (self-hosted wiktorn on the
cluster).

## When to use

- Reproducing / debugging the large-area OSM download without hitting public Overpass limits.
- Validating an AOI the public endpoint throttles (e.g. one spanning several Bundesländer).
- Any local dev where you want an offline, deterministic OSM source.

## 1. Bring up the Overpass instance

Lives in the sibling repo **`osm-services`** (`../osm-services/services/overpass/`). That
repo owns all the wiktorn gotchas (init_done gating, stable-named `.osm.bz2`, `file://`
curl behaviour) — follow its `README.md` / the `stand-up-overpass-for-a-region` skill.
Two shapes:

- **Single region:** `./bootstrap.sh` (default Germany) or `REGION=… PBF_URL=… ./bootstrap.sh`.
- **Merged multi-region** (the COSMONAUT AOI = Sachsen + Sachsen-Anhalt + Brandenburg):
  download each Geofabrik `.pbf`, then `osmium merge a.pbf b.pbf c.pbf -o db/ost.osm.bz2`
  (dedups shared borders). In `.env`: `OVERPASS_PLANET_URL=file:///db/ost.osm.bz2`,
  `OVERPASS_PLANET_PREPROCESS=` empty, `OVERPASS_DIFF_URL=` empty (snapshot, no update
  feed). Then `docker compose up -d` and wait for `db/init_done` + `docker compose ps`
  healthy **before** querying.

The mirrored image `registry.hzdr.de/ufz/tb5-smm/met/wg7/osm-services/overpass:latest`
needs `docker login registry.hzdr.de` first (GitLab PAT, scope `read_registry`).

## 2. Point COSMONAUT at it

Set **`OVERPASS_URL`** — read by [`osm/source.py`](../../../cosmonaut_app/osm/source.py)
via `os.getenv` (soft, default = public). For the local mock stack put it in
[`env_dev_mock`](../../../env_dev_mock):

```dotenv
OVERPASS_URL="http://localhost:12345/api/interpreter"
```

**Use the FULL interpreter URL.** The client POSTs `OVERPASS_URL` *verbatim* — it does
**not** append `/interpreter`; a bare `…/api` 404s. (`12345` = `OVERPASS_PORT`.) The Celery
worker runs with `network_mode: host`, so `localhost:12345` is reachable from inside the
container — no `host.docker.internal` needed. No code change is required; the var is the
single wiring point.

## 3. Run a test

- **Full app:** `./dev_up mock`, then trigger an upload whose AOI is inside the served region.
- **Standalone (no app):** the measurement spike
  [`test/fixtures/compare_osm_backends.py`](../../../test/fixtures/compare_osm_backends.py)
  runs `OsmDownloader` directly and reports time / peak-RSS / feature count, with
  `--reference` for a route-equivalence diff:

  ```bash
  .venv/bin/python test/fixtures/compare_osm_backends.py \
      --overpass-url http://localhost:12345/api --epsg 25832 --membership <points.csv>
  ```

  ⚠️ **Opposite URL convention:** the script's `--overpass-url` is the osmnx-style **base**
  `…/api` (it appends `/interpreter` itself). Only the `OVERPASS_URL` env var takes the full
  interpreter URL.

## Validated (2026-06-24)

Merged SN/ST/BB snapshot imported on the mirrored image (67M nodes, border-dedup verified).
COSMONAUT fetch over a ~7,000 km² tri-state AOI: **12.6 s, 153 MB peak RSS, 97,674 road
features**, no throttling. Small-AOI diff local vs public: **route-equivalent** (802=802
features, 0 m geometry delta, identical sensor-routing connectivity).

## Gotchas (hard-won)

- **`OVERPASS_DIFF_URL=` empty did NOT disable auto-updates** until osm-services' compose was
  fixed: `${OVERPASS_DIFF_URL:-default}` substitutes the germany-updates default for an
  *empty* value too, so a "snapshot" instance silently ran the update loop and mutated its
  DB. The fix is `${VAR-default}` (no colon). Fixed in
  `../osm-services/services/overpass/docker-compose.yml`.
- **Don't `docker compose up` before the merge finishes.** The entrypoint accepts a `file://`
  copy and will import a half-written `.osm.bz2` → garbage. Merge to a temp name + atomic
  rename so the final file appears only when complete. (`osmium` needs `-f osm.bz2` if the
  temp name isn't `*.osm.bz2`, since it infers format from the extension.)
- **Long merges/imports survive session/terminal interruptions if run as `docker run -d`**
  (daemon-owned), not a foreground shell job.
- **A root-owned bind-mounted `db/`** (wiktorn runs as root) can be reset without host sudo:
  `docker run --rm --entrypoint chown -v …/db:/db <image> -R <uid>:<gid> /db`.

## Related

- [osm-backend](../systems/osm-backend.md) — the downloader this points at.
- osm-services: `../osm-services/services/overpass/README.md`; skill
  `stand-up-overpass-for-a-region`; k8s contract `docs/conventions/deployment-kubernetes.md`.
- Decision: [20260605-osm-overpass-direct-vs-osmnx](../../decisions/20260605-osm-overpass-direct-vs-osmnx.md).
