"""This module defines variables, dir structure and includes widely used functions.

The service-level variables (Postgres, Redis, object storage, Flask) are read and
validated by ``cosmo_suite.config`` at import time and re-exported here, so every
consumer keeps importing them from ``cosmonaut_app.config``. Only the variables the
framework does not know about are read here.
"""

import os

from cosmo_suite.config import DEBUG as DEBUG
from cosmo_suite.config import OBJECT_STORAGE_ACCESS_KEY as OBJECT_STORAGE_ACCESS_KEY
from cosmo_suite.config import OBJECT_STORAGE_BUCKET as OBJECT_STORAGE_BUCKET
from cosmo_suite.config import OBJECT_STORAGE_HOST as OBJECT_STORAGE_HOST
from cosmo_suite.config import OBJECT_STORAGE_REMOTE_NAME as OBJECT_STORAGE_REMOTE_NAME
from cosmo_suite.config import OBJECT_STORAGE_SECRET_KEY as OBJECT_STORAGE_SECRET_KEY
from cosmo_suite.config import PORT as PORT
from cosmo_suite.config import POSTGRES_DB as POSTGRES_DB
from cosmo_suite.config import POSTGRES_HOST_NAME as POSTGRES_HOST_NAME
from cosmo_suite.config import POSTGRES_PASSWORD as POSTGRES_PASSWORD
from cosmo_suite.config import POSTGRES_PORT as POSTGRES_PORT
from cosmo_suite.config import POSTGRES_USER as POSTGRES_USER
from cosmo_suite.config import REDIS_DB as REDIS_DB
from cosmo_suite.config import REDIS_HOST as REDIS_HOST
from cosmo_suite.config import REDIS_PASSWORD as REDIS_PASSWORD
from cosmo_suite.config import REDIS_PORT as REDIS_PORT
from cosmo_suite.config import WEB_OUTSIDE_URL as WEB_OUTSIDE_URL
from cosmo_suite.config import env_vars as framework_env_vars
from cosmo_suite.config import getenv
from cosmo_suite.constants.general import (
    DAYS_DELETE_NOT_SUBMITTED as DAYS_DELETE_NOT_SUBMITTED,
)
from cosmo_suite.constants.general import DAYS_DELETE_SUBMITTED as DAYS_DELETE_SUBMITTED

# Needed for the test_env.py. Update!
# The framework list is the service-level half; everything below is cosmonaut's own.
env_vars = framework_env_vars + [
    "DOCKER_UID",
    "DOCKER_GID",
    "GUNICORN",
    "OBJECT_STORAGE_PORT",
    "OBJECT_STORAGE_CONSOLE_PORT",
    "TILESERVER_URL",
    "MAINTAINER_EMAIL",
    "EMAIL_SERVER",
    "EMAIL_PORT",
    "EMAIL_USERNAME",
    "EMAIL_PASSWORD",
    "EMAIL_SENDER",
]

# Testing flag — set in env_test / env_test_local, absent in production.
# Deliberately os.getenv with a default instead of the strict getenv(): an absent
# value is the production case, not a misconfiguration.
COSMONAUT_TESTING = os.getenv("COSMONAUT_TESTING", "false") == "true"
# Not neeeded for service kept for testing
DOCKER_UID = getenv("DOCKER_UID")
DOCKER_GID = getenv("DOCKER_GID")
GUNICORN = getenv("GUNICORN")

# Web Application Configuration
# Deviation from the framework, on purpose: cosmo_suite.config leaves WEB_WORK_DIR as
# read from the environment, i.e. relative ("./cosmonaut_app/work_dir"). Flask's
# send_from_directory resolves a relative directory against app.root_path
# (= cosmonaut_app/), not the process CWD, so serving job pictures would 404. Resolve
# it once at import instead. Belongs in the framework — until then cosmo_suite.job and
# cosmo_suite.tasks.maintenance_tasks still see the relative form.
WEB_WORK_DIR = os.path.abspath(getenv("WEB_WORK_DIR"))
JOB_WORK_DIR_TEMPLATE = os.path.join(WEB_WORK_DIR, "{job_id}")
MAINTAINER_EMAIL = [e.strip() for e in getenv("MAINTAINER_EMAIL").split(",")]

# Tile Server URL
TILESERVER_URL = getenv("TILESERVER_URL")

# Email Configuration
EMAIL_SERVER = getenv("EMAIL_SERVER")
EMAIL_PORT = getenv("EMAIL_PORT")
EMAIL_USERNAME = getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = getenv("EMAIL_PASSWORD")
EMAIL_SENDER = getenv("EMAIL_SENDER")

# Object Storage — not needed for the service, kept for testing
OBJECT_STORAGE_PORT = getenv("OBJECT_STORAGE_PORT")
OBJECT_STORAGE_CONSOLE_PORT = getenv("OBJECT_STORAGE_CONSOLE_PORT")


def get_download_url(job_id, filename="route.gpx"):
    """Construct the full download URL for a GPX file.

    Args:
        job_id: Job identifier
        filename: Name of the file to download (default: "route.gpx")

    Returns:
        str: Full URL to download the file
    """
    if "localhost" in WEB_OUTSIDE_URL:
        url_base = WEB_OUTSIDE_URL + ":" + PORT
    else:
        url_base = WEB_OUTSIDE_URL
    return f"{url_base}/download/{job_id}/{filename}"
