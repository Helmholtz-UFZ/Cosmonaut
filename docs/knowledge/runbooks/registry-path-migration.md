# Runbook — Registry Path Migration (`ufz-cosmonaut` → `cosmonaut`)

Renaming the GitLab project path also moves the container registry path. GitLab
refuses the rename while container image tags exist:

```
Cannot rename project, the container registry path rename validation failed: Rename Not Supported
```

HIFIS (Christian, ticket 2026-08) confirmed there is no server-side move: the only
route is [pull → delete → rename → push](https://docs.gitlab.com/user/packages/container_registry/troubleshoot_container_registry/#unable-to-change-project-path-or-transfer-a-project).
Background and the reason the path is hardcoded in exactly one place:
[conventions/registry_and_rename.md](../../conventions/registry_and_rename.md).

## State — update this section as the migration proceeds

**Paused since 2026-08-17, before the destructive step.**

| | Zustand | muss zurückgesetzt werden |
|---|---|---|
| ArgoCD Auto-Sync | **aus** (Robin Zinke, RDM) | ja — auf den neuen Pfad zeigen, dann einschalten |
| Schedule 546 `renew latest release image` | **deaktiviert** | **ja** |
| Schedule 536 `Daily OSM Overpass live check` | **deaktiviert** | **ja** |
| GitLab `path` | unverändert `ufz-cosmonaut` | — |
| GitLab `name` | schon `Cosmonaut` | — |
| Registry-Tags | unverändert (17 / 103 / 103 / 1) | — |
| Prod läuft auf | `0.3.3-2026.08.16` | — |

Nothing destructive has happened yet. Both schedules being off is the only thing
that silently degrades over time: no nightly rebuild means no base-image security
patches. **If this migration is abandoned, re-enable them anyway:**

```bash
glab api -X PUT projects/11247/pipeline_schedules/546 -f active=true
glab api -X PUT projects/11247/pipeline_schedules/536 -f active=true
```

## What gets preserved, what is lost

Nine image tags, not all 224. Prod needs one pair, the rest are rollback anchors:

| Tag | frontend | worker |
|---|---|---|
| `0.3.3-2026.08.16` | ✓ runs in prod | ✓ |
| `0.3.3` | ✓ | ✓ |
| `0.3.2-2026.08.12` | ✓ | ✓ |
| `0.3.2` | ✓ | ✓ |

Plus `ci:latest` — required, because `build-ci-image` only runs on the default
branch ([.gitlab-ci.yml:67](../../../.gitlab-ci.yml#L67)), so a tag pipeline would
fail pulling it.

Deliberately lost: ~95 date variants per image and 17 tags in the legacy
repository sitting directly on the project path (`ufz-cosmonaut:0.0.x`, 01/2025,
predates the frontend/worker split).

## The trap — a new git tag is mandatory afterwards

`build-latest-tag` does `git checkout $(git describe --tags --abbrev=0)` and
`bump_version_for_cluster` commits that checkout's `values.yaml` back to main with
`git pull --strategy-option=ours` ([.gitlab-ci.yml:299](../../../.gitlab-ci.yml#L299)).
Tag `0.3.3` still contains the **old** registry path, so the next nightly would
revert the path fix and point ArgoCD at a dead registry path. **After fixing
`values.yaml`, cut a new tag.** Same mechanism as
[conventions/deployment.md § values.yaml image tag is automated](../../conventions/deployment.md).

## Do not prune Docker between steps 2 and 4

Between deletion and re-push, the nine images in the local Docker daemon are the
only copies that exist. `docker image prune -a` and `docker system prune` both
remove images no container references — i.e. exactly those nine. Losing them means
the deployed prod state is gone and must be rebuilt from main. The local volumes
(~24 GB) are the dev Postgres/MinIO data — never `prune --volumes`.

Disk: ~7.5 GB gross, less after layer sharing. Verified 88 GB free (2026-08-17).

## Procedure

### Before the window — no risk, no time pressure

1. Disable both schedules (see table above, `active=false`).
2. Run step 1 of the scripts below. Verify nine images are present locally.

### The window — a pod restart here means `ImagePullBackOff`

Running pods are unaffected (image is on the node), but the worker uses
`pullPolicy: Always` ([values.yaml:76](../../../deployment/ufz/prod/values.yaml#L76)),
so any restart in this window fails to pull.

3. Robin: ArgoCD auto-sync off.
4. Delete all tags in all four registry repositories. Wait until `tags_count`
   reports 0 everywhere — GitLab cleans up asynchronously and the rename stays
   blocked until then. **Open question for HIFIS: does the rename validation pass
   as soon as the tags are gone via API, or does a cleanup job have to run first?**
   That answer determines the window length.
5. Rename `path` → `cosmonaut` (Settings → General → Advanced → Change path).
   No HIFIS involvement needed once the tags are gone.
6. Push the nine images to the new path, repoint the git remote, fix the two
   `repository:` lines in `deployment/ufz/prod/values.yaml`, commit, push.
7. **Cut a new git tag** (`0.3.4`) — see the trap above. Its pipeline also builds
   fresh images at the new path.
8. Robin: point ArgoCD at the new path, auto-sync on, verify prod.
9. **Re-enable both schedules** (`active=true`).
10. Update this file and `docs/project-state.md`.

## Scripts

`PROJ=11247`; registry repository ids `21306` (legacy root), `26185` (frontend),
`26186` (worker), `26866` (ci).

### 1 — pull and retag (safe, repeatable)

```bash
OLD="registry.hzdr.de/ufz/tb5-smm/met/wg7/ufz-cosmonaut"
NEW="registry.hzdr.de/ufz/tb5-smm/met/wg7/cosmonaut"
TAGS=(0.3.3-2026.08.16 0.3.3 0.3.2-2026.08.12 0.3.2)

for img in frontend worker; do
  for t in "${TAGS[@]}"; do
    docker pull "${OLD}/${img}:${t}"
    docker tag  "${OLD}/${img}:${t}" "${NEW}/${img}:${t}"
  done
done
docker pull "${OLD}/ci:latest" && docker tag "${OLD}/ci:latest" "${NEW}/ci:latest"

docker images "${NEW}/*" --format '{{.Repository}}:{{.Tag}}  {{.Size}}'   # expect 9
```

### 2 — delete all tags (irreversible)

```bash
for repo in 21306 26185 26186 26866; do
  for round in $(seq 1 20); do
    # after each deletion the pages shift, so always refetch page 1
    tags=$(glab api "projects/11247/registry/repositories/${repo}/tags?per_page=100" \
             | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
    [[ -z "$tags" ]] && break
    while read -r t; do
      [[ -z "$t" ]] && continue
      glab api -X DELETE "projects/11247/registry/repositories/${repo}/tags/${t}" >/dev/null \
        || echo "!! failed: ${repo}/${t}"
    done <<< "$tags"
  done
done

# must read 0 everywhere before attempting the rename
glab api "projects/11247/registry/repositories?tags_count=true" \
  | tr '}' '\n' | grep -oE '"path":"[^"]*"|"tags_count":[0-9]+' | paste - -
```

### 3 — after the rename

```bash
NEW="registry.hzdr.de/ufz/tb5-smm/met/wg7/cosmonaut"
TAGS=(0.3.3-2026.08.16 0.3.3 0.3.2-2026.08.12 0.3.2)

# preflight: abort if any image went missing — it is already gone from the registry
for img in frontend worker; do
  for t in "${TAGS[@]}"; do
    docker image inspect "${NEW}/${img}:${t}" >/dev/null || exit 1
  done
done
docker image inspect "${NEW}/ci:latest" >/dev/null || exit 1

for img in frontend worker; do
  for t in "${TAGS[@]}"; do docker push "${NEW}/${img}:${t}"; done
done
docker push "${NEW}/ci:latest"

git remote set-url origin git@codebase.helmholtz.cloud:ufz/tb5-smm/met/wg7/cosmonaut.git
git switch main && git pull --ff-only
sed -i 's|met/wg7/ufz-cosmonaut/frontend|met/wg7/cosmonaut/frontend|
        s|met/wg7/ufz-cosmonaut/worker|met/wg7/cosmonaut/worker|' \
  deployment/ufz/prod/values.yaml
git diff -- deployment/ufz/prod/values.yaml   # exactly two lines

# commit path-limited — never `git commit -am` here, it would sweep up whatever
# else the branch switch carried into the working tree
git commit -m "Point the prod images at the renamed registry path" \
  -- deployment/ufz/prod/values.yaml
git push
```

### Abort path — only before the rename

`docker tag` in step 1 *adds* a tag, so the local daemon still holds the images
under the **old** path as well. As long as the rename has **not** happened, the
status quo is therefore restorable:

```bash
OLD="registry.hzdr.de/ufz/tb5-smm/met/wg7/ufz-cosmonaut"
for img in frontend worker; do
  for t in 0.3.3-2026.08.16 0.3.3 0.3.2-2026.08.12 0.3.2; do
    docker push "${OLD}/${img}:${t}"
  done
done
docker push "${OLD}/ci:latest"
```

This is what makes it defensible to enter the window without knowing whether a
registry cleanup job has to run first — worst case the nine tags go back where
they were and prod is pullable again.

**Once the rename is through, this escape hatch is gone**: the old registry path
no longer exists, so nothing can be pushed back to it. From that point the only
way is forward.

## `write_registry` — verify the token BEFORE deleting anything

The push failed on the first attempt with `denied: requested access to the
resource is denied` for all nine images, with the registry already emptied and
the project already renamed — i.e. at the one moment where there is no way back.
Cause: the stored `docker login` credential was a Personal Access Token with
`read_registry` but **not** `write_registry`. Pulls had therefore always worked
and nothing signalled the gap. Project role is irrelevant here (Owner,
`access_level: 50`), and GitLab cannot add a scope to an existing token — a new
one has to be created.

Check this in step 1, not in step 6:

```bash
glab api personal_access_tokens/self | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['scopes'])"
```

`write_registry` must be in that list, and the token that `docker login` uses must
be the one carrying it (`~/.docker/config.json`, `auths['registry.hzdr.de']`).
