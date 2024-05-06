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


load_dotenv(".env_test_priv")

WEB_WORK_DIR = getenv("WEB_WORK_DIR")
PORT = getenv("FLASK_PORT")
MINIO_ACCESS_KEY = getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = getenv("MINIO_SECRET_KEY")


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
