# Decision: What the Public GitHub Mirror May Expose

**Date:** 2026-08-12
**Status:** Accepted
**Context:** SoftwareX metadata C2 requires a public GitHub repository ("We will not
proceed with your paper otherwise"). Work continues on GitLab; GitHub becomes a push
mirror with **full history**. Before the first public push the tracked tree was
audited for credentials and internal infrastructure.

## Finding: no credentials, but real identifiers

Every password and secret key is absent from the tracked tree. They come from the
sealed Kubernetes secret `app.secrets` (`EMAIL_PASSWORD`,
`OBJECT_STORAGE_SECRET_KEY`, `POSTGRES_PASSWORD`) or from the gitignored
`env_dev_prod_priv`. The one line that looked like an SMTP password —
`env_dev_prod`'s 34-character `EMAIL_PASSWORD`, flagged because it carried no
placeholder marker — is a five-word instruction whose last word is
`env_dev_prod_priv`. It is a placeholder. **No history rewrite, nothing to rotate.**

What `env_prod` does carry, and will be public:

| | |
|---|---|
| `OBJECT_STORAGE_ACCESS_KEY` | a real access key **ID** (21 chars, `AKIA` prefix) for `vip.s3.ufz.de` |
| `EMAIL_USERNAME` + `EMAIL_SERVER` | the service account and the mail relay |
| `POSTGRES_USER` + `POSTGRES_HOST_NAME` | a role name on an internal database host |
| `WEB_OUTSIDE_URL`, `TILESERVER_URL` | internal-only application hostnames |

Note this **corrects the pre-mirror plan**, which assumed the access key was "probably
a speaking account name, not a secret". It is not a speaking name; it is a real key
ID. The plan's conclusion still holds, but for a different reason than it gave.

## Decision

**Leave `env_prod` unchanged.** Publish it as is.

Two reasons:

1. **An access key ID is an identifier, not a credential.** It is transmitted in the
   clear in every signed S3 request and appears in server logs by design; access
   requires the secret key, which is sealed. The same is true of a mail service
   account without its password and a database role without its password.
2. **Replacing them would break production for no security gain.** `env_prod` is
   baked into the image (`COPY env_prod .env` in `docker/prod.Dockerfile` and
   `docker/worker.Dockerfile`), and none of these four values is in `app.secrets` or
   `values.yaml`. Placeholdering them without first sealing them would remove them
   with no replacement — a real outage traded for a cosmetic improvement.

The alternative — moving them into the sealed secret — stays available and is the
right move *if* the exposure ever becomes a concern. It needs the cluster sealing key
and a production rollout, so it is a deliberate operation, not a side effect of
preparing a mirror.

## What was scrubbed instead

Only where it costs nothing and breaks nothing:

- **`docker/init.sql`** spelled out two internal database hosts and four admin role
  names in copy-pasteable `psql` commands, inside a comment block. This was not in
  the audit plan's list — the grep pass found it. Replaced with placeholders; nothing
  reads comments.
- **`env_dev_prod`** is a template: only `test_env.py` consumes it, while
  `dev_up.sh prod` reads the gitignored `env_dev_prod_priv`, which already carries
  every real value. Mail relay and service account, object-storage access key and
  host, database host and user are now the same `fill and copy to env_dev_prod_priv`
  placeholder the file already used for its passwords.

`MAINTAINER_EMAIL` needed nothing — the departed maintainer's address is already gone
from all five env files. Personal `@ufz.de` addresses stay: metadata C8 publishes them
as the paper's support contact, so removing them from the repo would buy nothing.
`codebase.helmholtz.cloud` URLs stay too — that is where the work happens; only
installation instructions must point at GitHub.

## Consequences

- The mirror can carry full history. No rewrite, no rotation, no blocked release.
- **If the S3 access key is ever rotated, or the mail account changes, this decision
  should be revisited** — the cheap moment to move these into the sealed secret is
  while someone is touching them anyway.
- Anyone reading `env_prod` learns which internal hosts exist. That is accepted:
  those hosts are not reachable from outside, and the alternative costs an outage.
