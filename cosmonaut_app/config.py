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
    "REDIS_DB",
    "OBJECT_STORAGE_ACCESS_KEY",
    "OBJECT_STORAGE_SECRET_KEY",
    "OBJECT_STORAGE_HOST",
    "OBJECT_STORAGE_BUCKET",
    "OBJECT_STORAGE_REMOTE_NAME",
    "POSTGRES_NAME",
    "POSTGRES_HOST_NAME",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DOCKER_UID",
    "DOCKER_GID",
    "DEBUG",
    "WEB_OUTSIDE_URL",
    "OBJECT_STORAGE_PORT",
    "OBJECT_STORAGE_CONSOLE_PORT",
    "TILESERVER_URL",
    "MAINTAINER_EMAIL",
    "EMAIL_SERVER",
    "EMAIL_PORT",
    "EMAIL_USERNAME",
]

# Devolopment Debug Mode
DEBUG = getenv("DEBUG") == "1"
# Not neeeded for service kept for testing
DOCKER_UID = getenv("DOCKER_UID")
DOCKER_GID = getenv("DOCKER_GID")
GUNICORN = getenv("GUNICORN")

# Web Application Configuration
WEB_WORK_DIR = os.path.abspath(getenv("WEB_WORK_DIR"))
JOB_WORK_DIR_TEMPLATE = os.path.join(WEB_WORK_DIR, "{job_id}")
WEB_OUTSIDE_URL = getenv("WEB_OUTSIDE_URL")
FLASK_PORT = getenv("FLASK_PORT")
MAINTAINER_EMAIL = getenv("MAINTAINER_EMAIL")

# Tile Server URL
TILESERVER_URL = getenv("TILESERVER_URL")

# Email Configuration
EMAIL_SERVER = getenv("EMAIL_SERVER")
EMAIL_PORT = getenv("EMAIL_PORT")
EMAIL_USERNAME = getenv("EMAIL_USERNAME")

# Object Storage Configuration (rclone-based S3)
OBJECT_STORAGE_ACCESS_KEY = getenv("OBJECT_STORAGE_ACCESS_KEY")
OBJECT_STORAGE_SECRET_KEY = getenv("OBJECT_STORAGE_SECRET_KEY")
OBJECT_STORAGE_HOST = getenv("OBJECT_STORAGE_HOST")
OBJECT_STORAGE_BUCKET = getenv("OBJECT_STORAGE_BUCKET")
OBJECT_STORAGE_REMOTE_NAME = getenv("OBJECT_STORAGE_REMOTE_NAME")
# Not neeeded for service kept for testing
OBJECT_STORAGE_PORT = getenv("OBJECT_STORAGE_PORT")
OBJECT_STORAGE_CONSOLE_PORT = getenv("OBJECT_STORAGE_CONSOLE_PORT")

# PostgreSQL Configuration
POSTGRES_NAME = getenv("POSTGRES_NAME")
POSTGRES_HOST_NAME = getenv("POSTGRES_HOST_NAME")
POSTGRES_PORT = getenv("POSTGRES_PORT")
POSTGRES_USER = getenv("POSTGRES_USER")
POSTGRES_PASSWORD = getenv("POSTGRES_PASSWORD")

# Redis Configuration
REDIS_PORT = getenv("REDIS_PORT")
REDIS_HOST = getenv("REDIS_HOST")
REDIS_DB = getenv("REDIS_DB")
REDIS_PASSWORD = getenv("REDIS_PASSWORD")


def get_download_url(job_id, filename="route.gpx"):
    """Construct the full download URL for a GPX file.

    Args:
        job_id: Job identifier
        filename: Name of the file to download (default: "route.gpx")

    Returns:
        str: Full URL to download the file
    """
    if "localhost" in WEB_OUTSIDE_URL:
        url_base = WEB_OUTSIDE_URL + FLASK_PORT
    else:
        url_base = WEB_OUTSIDE_URL
    return f"{url_base}/download/{job_id}/{filename}"
