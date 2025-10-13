"""This module defines variables, dir structure and includes widely used functions."""

import os

from dotenv import load_dotenv
from pathlib import Path


def getenv(name):
    """
    Retrieve the value of an environment variable.

    This function is a wrapper around the `os.getenv` function and provides additional
    error handling by raising a `ValueError` if the requested environment variable is
    not set.
    """
    value = os.getenv(name)

    if value is None:
        raise ValueError(f"Enviroment variable {name} not set.")
    return value


# Number of days to keep a submitted job entries in the database
DAYS_DELETE_SUBMITTED = 60
# Number of days to keep an unsubmitted job entries in the database
DAYS_DELETE_NOT_SUBMITTED = 2

# Load base .env, then (only outside Docker) overlay a developer-specific .env.local.
# This lets local runs (uv) use localhost services while Docker keeps using the
# environment provided by docker-compose/.env without being overridden.
project_root = Path(__file__).resolve().parents[1]
base_env = project_root / ".env"
local_env = project_root / ".env.local"


def _in_docker() -> bool:
    """Best-effort detection of Docker runtime.

    We rely on the presence of '/.dockerenv' which is standard for Docker.
    """
    return Path("/.dockerenv").exists()


# Load base first (no override), then overlay local (override=True)
if base_env.exists():
    # Load base file but do not override variables already set by the environment
    # (e.g., injected by docker-compose env_file / environment).
    load_dotenv(dotenv_path=str(base_env), override=False)

# Only overlay the developer overrides when NOT running in Docker
if not _in_docker() and local_env.exists():
    load_dotenv(dotenv_path=str(local_env), override=True)
elif not base_env.exists():
    # Fallback to default discovery if no explicit files found
    load_dotenv()

WEB_WORK_DIR = getenv("WEB_WORK_DIR")
FLASK_PORT = getenv("FLASK_PORT")
REDIS_PORT = getenv("REDIS_PORT")
REDIS_HOST = getenv("REDIS_HOST")
MINIO_ACCESS_KEY = getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = getenv("MINIO_SECRET_KEY")
MINIO_HOST = getenv("MINIO_HOST")
MINIO_PORT = getenv("MINIO_PORT")
DB_NAME = getenv("DB_NAME")
DB_HOST_NAME = getenv("DB_HOST_NAME")
DB_PORT = getenv("DB_PORT")
DB_USER = getenv("DB_USER")
DB_PW = getenv("DB_PW")
DOCKER_UID = getenv("DOCKER_UID")
DOCKER_GID = getenv("DOCKER_GID")

# Mapping of OSM tags to the corresponding road classes
osm_tags_mapping = {
    "Autobahn": ["motorway", "motorway_link"],
    "Schnellstraße": ["trunk", "trunk_link"],
    "Bundesstraßen": ["primary", "primary_link"],
    "Landstraße": ["secondary", "secondary_link"],
    "Kreisstraße": ["tertiary", "tertiary_link"],
    "Gemeindestraße": ["unclassified"],
    "Wohnstraße": ["residential"],
    "Spielstraße": ["living_street"],
    "Wirtschaftsweg": ["track"],
}
