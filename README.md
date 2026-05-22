<div>
<h1 align="center">COSMONAUT</h1>
<h2 align="center"><strong>COS</strong><small>mic ray based soil </small><strong>MO</strong><small>isture </small><strong>P</strong><small>rediction </small><strong>NA</strong><small>vigation and </small><strong>UT</strong><small>ility </small><strong>T</strong><small>ool</small></h2>
<p align="center">
	<img src="cosmonaut_app/static/front_banner.png" alt="Welcome" width="30%">
</p>
</div>

COSMONAUT is a Python-based web application designed to optimize navigation routes for mobile Cosmic Ray Neutron Sensor (CRNS) rover surveys.

COSMONAUT implements a seven-step guided workflow that transforms membership classification data into field-ready navigation routes. Each step is presented as a separate page within the web interface, preserving state in a PostgreSQL database to enable researchers to pause and resume work at any time.

The service is primarily built using Plotly Dash and uses Celery for background and
resource intensive tasks. Three databases are used: PostgreSQL as main storage, MinIO for
object storage, and Redis as the broker between the Dash server and workers.

## Quick Start

```bash
# Mock development (no external services)
./dev_up.sh mock

# Production development (requires credentials)
cp env_dev_prod env_dev_prod_priv
# Edit credentials in env_dev_prod_priv
./dev_up.sh prod
```

## Technical Architecture

COSMONAUT's architecture balances scientific workflow requirements with software engineering best practices, implementing a multi-tier system suitable for both single-user local deployments and multi-tenant institutional servers.

### Technology Stack

**Frontend Framework**: Dash 2.x (plotly/dash) provides the reactive web interface entirely in Python, eliminating JavaScript for core functionality. The multi-page application structure uses Dash's `use_pages=True` plugin for automatic route registration: adding a new workflow step requires only creating a file in `pages/` with `register_page()` decorator.

**Interactive Mapping**: Dash Leaflet (thedirtyfew/dash-leaflet) wraps Leaflet.js for Python-native geospatial visualization. COSMONAUT leverages GeoJSON layers with click event handling, dynamic style functions (JavaScript-like Python syntax via dash-extensions `assign()`), and multiple tile providers.

**Backend Services**: PostgreSQL 15 stores job metadata in a relational schema. The `jobs` table includes columns for job_id (primary key), email, status (enum), start_date, last_modified, epsg_code, and a flexible `config` JSONB field storing the complete Pydantic model of the routing algorithm as JSON. Further all logs of the service are stored in the database.

**Message Queue**: Redis 7 with Celery 5.x implements the distributed task queue for route computation. Celery workers run in separate Docker containers (cosmonaut-worker) with identical Python environment but isolated process space. The architecture supports task prioritization (routing queue for user jobs, maintenance queue for cleanup tasks), task cancellation, and health monitoring.

**Object Storage**: MinIO (S3-compatible) provides durable file storage independent of container lifecycles. Each job's working directory uploads to MinIO bucket `cosmonaut-jobs/{job_id}/` via rclone synchronization. This enables stateless web container design (containers can restart without data loss).

**Containerization**: Docker Compose orchestrates five services (cosmonaut web, cosmonaut-worker, postgres, redis, minio) with health checks and dependency ordering.

**Local Deployment**: The simplest deployment method is to clone the repository and execute `docker compose up` or better `./dev_up.sh mock` which copies the required env file in the project root. This single command provisions a complete local instance with all required services (Dash web application, Celery workers, PostgreSQL, Redis, MinIO) pre-configured with networking and health checks. A fully functional route planning environment is available within minutes, suitable for local development, evaluation, and institutional pilot deployments.

**Production Deployment**: In production the service is deployed on a Kubernetes
cluster. Here only the services cosmonaut-web, cosmonaut-worker, Redis, and the
tileserver are used, as the permanent storages PostgreSQL and MinIO are managed by the
infrastructure of the institute.

## sensor-routing

### Local development

Develop against a local checkout of sensor-routing (must be a sibling directory `../sensor-routing`):

```bash
./dev_up.sh --local-sr mock
```

Changes to sensor-routing Python files auto-reload the Dash server. The Celery worker requires a container restart.

### Updating the PyPI version

1. Edit `pyproject.toml` to new version.
2. Maybe `uv cache clean sensor-routing` if update was just a few minutes ago.
3. `uv lock`
4. If you have local python evn `uv sync`.
5. `./dev_up.sh` will detect changes in `uv.lock` and rebuild container.

## More Detailed Documentation

The `docs/` directory contains in-depth guides covering project conventions and LLM-assisted development workflows.

### Conventions

These documents define the coding standards and architectural patterns used throughout the project. They serve as the single source of truth for both human contributors and AI assistants.

- [HTML IDs](docs/conventions/html_ids.md) - Rules for when and how to create HTML element IDs using centralized constants.
- [Callbacks](docs/conventions/callbacks.md) - Patterns for organizing page-specific and shared Dash callbacks.
- [Error Handling](docs/conventions/error_handling.md) - Centralized error handling with custom exceptions and an error modal.
- [Logging](docs/conventions/logging.md) - Proper logger setup and log level conventions.
- [Layout](docs/conventions/layout.md) - Reusable layout components and flex patterns for page structure.
- [Bootstrap Styling](docs/conventions/bootstrap_styling.md) - Use Bootstrap classes exclusively instead of inline CSS.
- [Testing](docs/conventions/testing.md) - Integration testing with Playwright and the CI pipeline setup.
- [Environment Variables](docs/conventions/environment_variables.md) - Environment files, config loading, and strict variable validation.

### LLM

These are skill documents and configuration files designed for AI-assisted development with Claude Code. They provide step-by-step instructions that LLMs follow when performing common development tasks.

- [CLAUDE.md](CLAUDE.md) - Project conventions and guidelines for AI assistants working on this codebase.
- [New Page](docs/skills/new_page.md) - Step-by-step checklist for adding a new page to the Dash application.
- [Create Playwright Test](docs/skills/create_playwright_test.md) - Checklist for adding a Playwright integration test.
- [Create Module Test](docs/skills/create_module_test.md) - Checklist for adding an integration test for a core module without Playwright.
- [Run and Fix Testing](docs/skills/run_and_fix_testing.md) - Guide for running tests, diagnosing failures, and applying fixes.
- [Convention Keeper](docs/skills/convention_keeper.md) - Systematic audit of the codebase against all project conventions.
- [Adopt User-Generated Playwright Test](docs/skills/adopt_user_generate_playwright_test.md) - Prompt for cleaning up tests generated with the codegen tool.

## Design

- [Design System](docs/design-system/README.md) — Tokens, brand voice, UI kit, iconography.
