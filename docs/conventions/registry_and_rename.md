# Container Registry & Project Rename

Images live in the GitLab registry at `registry.hzdr.de/ufz/tb5-smm/met/wg7/ufz-cosmonaut/{frontend,worker,ci}`.
ArgoCD watches `deployment/ufz/prod/values.yaml`.

## The registry path appears in exactly one place

Everything in `.gitlab-ci.yml` derives the path at runtime — `${CI_REGISTRY_IMAGE}`
for images, `${CI_PROJECT_PATH}` for the push remote. The **only** hardcoded
occurrences are the two `repository:` lines in `deployment/ufz/prod/values.yaml`
(frontend + worker). A project rename therefore needs no CI changes, only those
two lines.

## Renaming the project is blocked by the registry

Attempting the rename (Settings → General → Advanced → Change path) fails with:

```
Cannot rename project, the container registry path rename validation failed: Rename Not Supported
```

The registry refuses to move the repository path, even though its GitLab API is
reachable (`https://registry.hzdr.de/gitlab/v1/` answers 401, not 404). This is
instance-side and owned by the Wombat/RDM team — not fixable from this repo.

Known facts, so this doesn't get re-investigated:

- GitLab's *Name* (display) can be changed freely — only the *Path* triggers the
  registry validation.
- Deleting all container images in the project skips the validation, but costs the
  full tag history (~200 tags) and opens a window where prod cannot pull. The
  worker uses `pullPolicy: Always`, so a pod restart in that window means
  `ImagePullBackOff`. Image deletion is also asynchronous — the rename stays
  blocked until GitLab's cleanup job has run.
- Argo watches the old path. Any path move requires the RDM team to disable
  auto-sync first, and to re-point + re-enable it afterwards.

Recorded 2026-08-12 after the attempt failed.

## Never touch values.yaml while a release pipeline runs

`bump_version_for_cluster` commits its own `values.yaml` artifact and does
`git pull origin main --strategy-option=ours` before pushing — a concurrent edit
to that file is silently discarded. Wait for the pipeline to go green, pull, then
edit. See also the tag-checkout revert trap in
[deployment.md](deployment.md#valuesyaml-image-tag-is-automated--re-tag-after-infra-changes).
