# syntax=docker/dockerfile:1
# Pre-built CI image — bakes in system dependencies, Python packages, and Playwright.
# Rebuilt in the pipeline when uv.lock, pyproject.toml, or this file changes.

FROM python:3.13-slim

ENV TZ=Europe/Berlin
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
# Isolated venv so PATH-based tools (pytest, playwright) work without uv run
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Fixed location for Playwright browsers, independent of the running user
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgdal-dev postgresql-client curl rclone && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv $VIRTUAL_ENV && pip install --no-cache-dir uv

WORKDIR /ci

COPY pyproject.toml uv.lock ./

RUN uv export --format requirements-txt --no-hashes > /tmp/lock-reqs.txt \
    && uv pip install -r /tmp/lock-reqs.txt

RUN playwright install --with-deps chromium
