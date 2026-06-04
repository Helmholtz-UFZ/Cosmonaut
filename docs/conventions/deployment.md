# Deployment Conventions

Production runs on Kubernetes (UFZ cluster, ArgoCD). This doc covers non-obvious
gotchas that don't surface in local docker-compose development.

## Gunicorn

- **Always set `--timeout` explicitly.** The default is 30 seconds — enough for
  normal page loads but not for long-running callbacks (file upload + rclone sync
  + plot generation can exceed 30s on large files). Production uses `--timeout 300`.
- **Use `-w 2`, not `-w 4`.** With `--preload`, each additional worker adds ~150–200 MB
  overhead on top of the already-large app baseline (geo imports: osmnx, geopandas,
  etc.). Four workers OOMKilled the frontend pod during large file uploads.

```dockerfile
# prod.Dockerfile
CMD ... gunicorn --preload -w 2 -b 0.0.0.0:$FLASK_PORT --timeout 300 cosmonaut_app.app:server
```

## HAProxy Ingress

Two annotations are required in `deployment/ufz/prod/values.yaml`:

```yaml
haproxy-ingress.github.io/proxy-body-size: "50m"   # dcc.Upload sends files as base64 — 12 MB file ≈ 17 MB payload
haproxy-ingress.github.io/timeout-server: "300s"   # must match Gunicorn timeout
```

Without `proxy-body-size`, HAProxy silently drops large request bodies (no 413, just
a hang). Without `timeout-server`, HAProxy cuts connections before Gunicorn finishes.

## Resource Limits

```yaml
# frontend pod — deployment/ufz/prod/values.yaml
resources:
  limits:
    cpu: 1000m   # 500m was too low — upload processing (CSV parse, plot gen, rclone) got throttled
    memory: 2Gi  # 1Gi OOMKilled on large file uploads
  requests:
    cpu: 200m
    memory: 512Mi
```

## Shared PVC

Both the frontend and worker pods mount the **same** PVC (`cosmonaut-work-dir-pvc`)
at `/python_docker/cosmonaut/cosmonaut_app/work_dir`. They share a filesystem on the
cluster — unlike local docker-compose where the bind mount achieves the same thing.

This matters for the object storage sync strategy: `--ignore-existing` (used in
layout-level `get_files()`) is safe because local edits on the shared volume won't be
overwritten by re-downloading the same files.

## Debugging Without kubectl

Direct `kubectl` access is not available — use the ArgoCD UI for pod events and logs.
When a pod restarts unexpectedly:
1. Check ArgoCD pod events for `OOMKilled` as the restart reason
2. Check previous container logs via the ArgoCD log viewer

OOMKill is the most common frontend crash and always shows the pattern:
"works with small files, crashes with large ones."

## values.yaml image tag is automated — re-tag after infra changes

The image tag in `deployment/ufz/prod/values.yaml` is **not** hand-maintained.
GitLab CI writes it back to `main`: `build-release` on a release tag, and
`build-latest-tag` → `bump_version_for_cluster` for the nightly rebuild (which
exists to pick up base-image / OS security patches — the daily image is
`<tag>-YYYY.MM.DD`).

The catch: `build-latest-tag` does `git checkout <latest git tag>` and commits
**that tag's** `values.yaml` back to main (with `git pull --strategy-option=ours`).
The tag predates your latest infra edits, so:

> **Any change made directly to `deployment/ufz/prod/values.yaml` on main —
> `ingress.className`, annotations, resources, env vars, … — is reverted by the
> next tag/nightly run, because the checked-out tag is older than your change.**

This already bit the sister project Cosmopolitan: an ingress `className` edit
(`nginx` → `haproxy`) was reverted by the nightly, producing a self-signed
`Kubernetes Ingress Controller Fake Certificate` + 404 while ArgoCD stayed
healthy.

### Rule

- **After any infra change to `values.yaml`, cut a new git tag** from main. The
  tag/nightly pipeline then checks out a tag that contains your change and stops
  reverting it.

### Nightly schedule

`build-latest-tag` / `bump_version_for_cluster` only run on a `web` trigger or
when gated by a dedicated schedule variable (e.g. `NIGHTLY_BUILD`). If you wire
up a nightly schedule, gate it on its **own** variable — keep it separate from
the OSM smoke-test schedule (`$OSM_TEST_SCHEDULE`), otherwise each schedule
triggers the other's job. Note this pipeline deploys **prod** (there is no
separate stage `values.yaml`), so a broken nightly build ships straight to prod
— keep dependencies pinned.
