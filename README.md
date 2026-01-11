<div>
<h1 align="center">COSMONAUT</h1>
<h2 align="center"><strong>COS</strong><small>mic ray based soil </small><strong>MO</strong><small>isture </small><strong>P</strong><small>rediction </small><strong>NA</strong><small>vigation and </small><strong>UT</strong><small>ility </small><strong>T</strong><small>ool</small></h2>
<p align="center">
	<img src="cosmonaut_app/static/front_banner.png" alt="Welcome" width="30%">
</p>
</div>

This project is a web application built with Dash and Dash Leaflet for transforming and visualizing CSV data for the COSMOPOLITAN Project at UFZ.
It allows users to upload a CSV file, transforms the data, queries OpenStreetMap for a planed navigation feature, and visualizes the csv-data on a map (NOTE: Visualization doesn`t work for bigger files)

## Features

- File upload: Users can upload a CSV file to the application.
- Data transformation: The application transforms the uploaded data from EPSG:31468 to EPSG:4326.
- OSM query: The application queries OpenStreetMap for roads within the convex hull of the uploaded data.
- Data visualization: The application visualizes the uploaded data and the queried OSM data on a map.
- It makes individual Jobs which are saved into a PostgreSQL DB.
- (Work) Is triggering a route calculation based on User Input of the best roads.

## Installation

### Quick Start

```bash
# Mock development (no external services)
./dev_up.sh mock

# Production development (requires credentials)
cp env_dev_prod env_dev_prod_priv
# Edit credentials in env_dev_prod_priv
./dev_up.sh prod
```

## Usage

### Local Development

```bash
# Start backend services (Postgres, Redis, MinIO)
docker compose up postgres redis minio -d

# Option 1: Use the provided script (prepares .env automatically)
./run_dev.sh

# Option 2: Manual setup
cp .env.local .env
uv run python -m cosmonaut_app.app
```

### Running Tests

```bash
# Run all tests (headless)
./run_pytest.sh

# Run all tests with visible browser
./run_pytest.sh --headed

# Run specific test file
./run_pytest.sh test/test_app.py

# Skip service startup (if already running)
./run_pytest.sh --no-services test/test_app.py
```

## Environment Configuration

The application uses different environment files:

- `env_dev_mock` - Enviroment for docker setup where all services are run locally.
- `env_dev_prod_priv` - Enviroment for docker setup where the production services are
  used. An can be found `env_dev_prod`.
- `env_test` - Testing enviroment for ci pipeline
- `env_test_local` - Testing enviroment for lokal testing
- `env_prod` - Enviroment for production deployment

Key environment variables:

- `FLASK_DEBUG=1` - Enable debug mode with auto-reload
- `GUNICORN=0` - Use Flask dev server instead of Gunicorn
- `WEB_WORK_DIR` - Working directory for job files
- `OBJECT_STORAGE_*` - Objet storage (minio/S3) configuration variables
- `DB_*` - Database connection settings (Postgres)
