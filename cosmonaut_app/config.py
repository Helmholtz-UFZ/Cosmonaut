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


load_dotenv()

WEB_WORK_DIR = getenv("WEB_WORK_DIR")
PORT = getenv("FLASK_PORT")
MINIO_ACCESS_KEY = getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = getenv("MINIO_SECRET_KEY")
