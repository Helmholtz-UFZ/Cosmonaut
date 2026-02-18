# Environment Variables

All environment variables are centralized in `cosmonaut_app/config.py`. They are
loaded via `python-dotenv` and validated at startup with a strict `getenv()`
wrapper that raises `ValueError` on any missing variable.

---

## Environment Files

| File | Purpose |
|------|---------|
| `.env` | Active file read by the app (symlinked or copied from a variant below) |
| `env_dev_mock` | Local dev with mocked services (MinIO, localhost) |
| `env_test` / `env_test_local` | Test environments (containerized vs localhost) |
| `env_dev_prod` | Dev against real staging services (needs secrets from `env_dev_prod_priv`) |
| `env_prod` | Production reference (secrets injected at deployment time) |
| `env_dev_prod_priv` | **Real credentials** — see [Secrets](#secrets) |

---

## Variable Categories

Grouped by service. The full list lives in `config.env_vars`.

- **Web / App**: `WEB_WORK_DIR`, `FLASK_PORT`, `DEBUG`, `GUNICORN`, `WEB_OUTSIDE_URL`
- **PostgreSQL**: `POSTGRES_NAME`, `POSTGRES_HOST_NAME`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- **Redis / Celery**: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`
- **Object Storage (S3/MinIO)**: `OBJECT_STORAGE_ACCESS_KEY`, `OBJECT_STORAGE_SECRET_KEY`, `OBJECT_STORAGE_HOST`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_REMOTE_NAME`, `OBJECT_STORAGE_PORT`, `OBJECT_STORAGE_CONSOLE_PORT`
- **Tileserver**: `TILESERVER_URL`
- **Email**: `MAINTAINER_EMAIL`, `EMAIL_SERVER`, `EMAIL_PORT`, `EMAIL_USERNAME`
- **Docker**: `DOCKER_UID`, `DOCKER_GID`

---

## How Config Loading Works

1. `config.py` calls `load_dotenv()` at import time.
2. The custom `getenv()` wrapper calls `os.getenv()` and raises `ValueError` if
   the variable is missing.
3. All values are stored as **module-level constants** — import them from
   `cosmonaut_app.config`.
4. The `config.env_vars` list enumerates every required variable. Tests use this
   list to validate completeness across all env files.

---

## Docker

How env vars reach containers (see `docker-compose.yml`):

- **App and worker containers**: `env_file: .env` passes all variables from the
  active `.env` file.
- **Postgres and MinIO**: `environment:` block with `${VAR}` interpolation maps
  project variables to the service's expected names (e.g.
  `MINIO_ROOT_USER: ${OBJECT_STORAGE_ACCESS_KEY}`).
- **Production Dockerfiles** (`docker/prod.Dockerfile`, `docker/worker.Dockerfile`):
  `COPY env_prod .env` bakes non-secret vars into the image; the CMD sources
  `.env` before starting the process.
- **`DOCKER_UID` / `DOCKER_GID`**: Used in `docker-compose.yml` via
  `user: "${DOCKER_UID}:${DOCKER_GID}"` for file permission mapping.

---

## Production Deployment (Kubernetes)

- `deployment/ufz/prod/values.yaml` injects env vars via `environmentVariables`
  on both frontend and worker pods.
- Secrets (`EMAIL_PASSWORD`, `OBJECT_STORAGE_SECRET_KEY`, `POSTGRES_PASSWORD`)
  are pulled from the K8s Secret `app.secrets` using `secretKeyRef`.
- The Secret is sealed with Bitnami SealedSecrets
  (`deployment/ufz/prod/app.sealedsecret.yaml`).
- Non-secret vars are baked into `env_prod` at image build time (see Docker
  section above).

---

## Secrets

- `env_dev_prod_priv` contains **real staging credentials** — **DO NOT** commit,
  share, or log this file.
- The file is listed in `.gitignore`.
- For production: secrets are managed via SealedSecrets, never stored in plain
  text.
- `object_storage_manager.py` masks `OBJECT_STORAGE_SECRET_KEY` with `"****"` in
  all subprocess output and error logs.

---

## Local sensor-routing Development (`--local-sr`)

The `--local-sr` flag on `dev_up.sh` lets you develop cosmonaut and sensor-routing
side by side without publishing to PyPI.

### How it works

1. `dev_up.sh --local-sr mock` layers `docker-compose.local-sr.yml` on top of
   the base compose file.
2. The override mounts `../sensor-routing` into both the `cosmonaut` and `worker`
   containers at `/python_docker/sensor-routing`.
3. `PYTHONPATH` is set so the local source shadows the PyPI-installed package.
4. `app.py` watches the mounted sensor-routing `.py` files via Flask's
   `extra_files` parameter, so the Dash dev server auto-reloads on changes.
5. The **Celery worker does not auto-reload** — restart it manually after
   sensor-routing changes (`docker compose restart worker`).

### Prerequisites

- The sensor-routing repo must be cloned as a **sibling directory**:
  `../sensor-routing` (flat layout, i.e. `../sensor-routing/sensor_routing/`).
- No changes to `pyproject.toml` or `uv.lock` are needed — the PYTHONPATH
  override takes precedence over the installed version.

### Files involved

| File | Role |
|------|------|
| `docker-compose.local-sr.yml` | Compose override: volume mount + PYTHONPATH |
| `dev_up.sh` | `--local-sr` flag builds the compose command with `-f` layering |
| `cosmonaut_app/app.py` | Watches `/python_docker/sensor-routing/sensor_routing/*.py` for reload |

---

## Testing & Adding New Variables

`test/test_env.py` validates that every env file contains all required variables.

How it works:
1. Iterates over all env files (`env_dev_mock`, `env_dev_prod`, `env_prod`,
   `env_test`, `env_test_local`).
2. For each file: copies it to `.env`, reloads with
   `load_dotenv(override=True)`, then checks every var in `config.env_vars` via
   `getenv()`.
3. For `env_prod` (where secrets are injected at deploy time), the test injects
   placeholder values for secret vars via `additional_lines_map`.

**Adding a new env var — checklist:**

1. Add the variable to **all 5 env files** (`env_dev_mock`, `env_dev_prod`,
   `env_prod`, `env_test`, `env_test_local`).
2. Add it to the `env_vars` list in `cosmonaut_app/config.py`.
3. Add a `getenv()` call and module-level constant in `config.py`.
4. If it is a secret in production, add it to `values.yaml` and
   `app.sealedsecret.yaml`.
5. If `env_prod` will not have the value at build time, add a placeholder line
   to `additional_lines_map` in `test/test_env.py`.
6. Run `./run_pytest.sh` — `test_env.py` will catch any missing vars.
