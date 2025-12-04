"""This module defines variables, dir structure and includes widely used functions."""

import os

from dotenv import load_dotenv


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

load_dotenv()

# Needed for the test_env.py. Update!
env_vars = [
    "WEB_WORK_DIR",
    "FLASK_PORT",
    "REDIS_PORT",
    "REDIS_HOST",
    "OBJECT_STORAGE_ACCESS_KEY",
    "OBJECT_STORAGE_SECRET_KEY",
    "OBJECT_STORAGE_HOST",
    "OBJECT_STORAGE_BUCKET",
    "OBJECT_STORAGE_REMOTE_NAME",
    "DB_NAME",
    "DB_HOST_NAME",
    "DB_PORT",
    "DB_USER",
    "DB_PW",
    "DOCKER_UID",
    "DOCKER_GID",
    "DEBUG",
]

WEB_WORK_DIR = getenv("WEB_WORK_DIR")
FLASK_PORT = getenv("FLASK_PORT")
REDIS_PORT = getenv("REDIS_PORT")
REDIS_HOST = getenv("REDIS_HOST")

# Object Storage Configuration (rclone-based S3)
OBJECT_STORAGE_ACCESS_KEY = getenv("OBJECT_STORAGE_ACCESS_KEY")
OBJECT_STORAGE_SECRET_KEY = getenv("OBJECT_STORAGE_SECRET_KEY")
OBJECT_STORAGE_HOST = getenv("OBJECT_STORAGE_HOST")
OBJECT_STORAGE_BUCKET = getenv("OBJECT_STORAGE_BUCKET")
OBJECT_STORAGE_REMOTE_NAME = getenv("OBJECT_STORAGE_REMOTE_NAME")
JOB_WORK_DIR_TEMPLATE = os.path.join(WEB_WORK_DIR, "{job_id}")

DB_NAME = getenv("DB_NAME")
DB_HOST_NAME = getenv("DB_HOST_NAME")
DB_PORT = getenv("DB_PORT")
DB_USER = getenv("DB_USER")
DB_PW = getenv("DB_PW")
DOCKER_UID = getenv("DOCKER_UID")
DOCKER_GID = getenv("DOCKER_GID")
DEBUG = getenv("DEBUG") == "1"

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
