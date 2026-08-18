# Container Registry & Project Rename

Images live in the GitLab registry at
`registry.hzdr.de/ufz/tb5-smm/met/wg7/cosmonaut/{frontend,worker,ci}`.
ArgoCD watches `deployment/ufz/prod/values.yaml`.

## The registry path appears in exactly one place

Everything in `.gitlab-ci.yml` derives the path at runtime — `${CI_REGISTRY_IMAGE}`
for images, `${CI_PROJECT_PATH}` for the push remote. The **only** hardcoded
occurrences are the two `repository:` lines in `deployment/ufz/prod/values.yaml`
(frontend + worker). A project rename therefore needs no CI changes, only those
two lines.

## Renaming the project: the registry blocks it, and how that was resolved

The path was `ufz-cosmonaut` until 2026-08-17. Changing it fails with:

```
Cannot rename project, the container registry path rename validation failed: Rename Not Supported
```

`registry.hzdr.de` refuses to move a repository path, even though its GitLab API is
reachable (`/gitlab/v1/` answers 401, not 404). HIFIS confirmed there is no
server-side move; the documented route is pull → delete → rename → push, which is
what was done. The full procedure, the two traps that cost time, and the end state
are in [knowledge/runbooks/registry-path-migration.md](../knowledge/runbooks/registry-path-migration.md).

Facts worth keeping, so none of this gets re-investigated:

- GitLab's *Name* (display) can be changed freely — only the *Path* triggers the
  registry validation.
- Deleting every container image in the project skips the validation. It costs the
  tag history and opens a window in which prod cannot pull; the worker uses
  `pullPolicy: Always`, so a pod restart in that window means `ImagePullBackOff`.
- **The rename is accepted as soon as the tags are gone via the API** — no cleanup
  job has to run in between. Measured on 2026-08-17: 224 tags deleted in one pass,
  rename accepted immediately. (An earlier note here assumed a cleanup wait; that
  was wrong.)
- The `docker login` credential needs **`write_registry`**, not just
  `read_registry`. Pulls work without it, so the gap only surfaces on the push —
  i.e. after the registry is already empty. Check the scope first.
- Argo watches the path. Any move needs the RDM team to disable auto-sync first and
  to re-point + re-enable it afterwards.

## Never touch values.yaml while a release pipeline runs

`bump_version_for_cluster` commits its own `values.yaml` artifact and does
`git pull origin main --strategy-option=ours` before pushing — a concurrent edit
to that file is silently discarded. Wait for the pipeline to go green, pull, then
edit. See also the tag-checkout revert trap in
[deployment.md](deployment.md#valuesyaml-image-tag-is-automated--re-tag-after-infra-changes).
