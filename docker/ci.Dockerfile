# syntax=docker/dockerfile:1
# Pre-built CI image — bakes in system dependencies, Python packages, and Playwright.
# Rebuilt in the pipeline when uv.lock, pyproject.toml, or this file changes.
#
# ENV ordering is intentional: only the ENVs actually required by each RUN step
# appear before it. Runtime-only ENVs (TZ, UV_NO_SYNC) live at the end so that
# changing them doesn't bust the cache for the expensive apt-get/pip/playwright layers.

FROM python:3.13-slim

# Isolated venv so PATH-based tools (pytest, playwright) work without uv run.
# Must precede the venv-creation and pip-install RUN steps.
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc g++ git libgdal-dev libpq-dev postgresql-client curl rclone && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv $VIRTUAL_ENV && pip install --no-cache-dir uv

WORKDIR /ci

COPY pyproject.toml uv.lock ./

# GDAL header paths required during pip compilation of GDAL Python bindings.
# Must precede the uv pip install step.
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

RUN uv export --format requirements-txt --no-hashes > /tmp/lock-reqs.txt \
    && uv pip install -r /tmp/lock-reqs.txt

# Fixed location for Playwright browsers, independent of the running user.
# Must precede playwright install so browsers land at this path.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN playwright install --with-deps chromium

# Runtime-only ENVs — do not affect any build step above, so they live last.
# Changing these busts only the final cheap ENV layer, not the expensive ones above.
ENV TZ=Europe/Berlin
# Skip venv sync when uv run is called from the project directory.
# The venv is pre-built in this image, so syncing is never needed and adds
# startup delay to subprocess-spawned commands (e.g. the Celery worker in conftest.py).
ENV UV_NO_SYNC=1
