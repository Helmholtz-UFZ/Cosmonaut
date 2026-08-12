"""Serve files from a directory.

Deliberately NOT replaced by ``cosmo_suite.files_route`` in slice 1. The framework
version is not a drifted copy of this one — it is a different route set:

- It has no ``/download/<job_id>/route.gpx`` route at all. That is the path the
  QR code and the notification mail point at.
- Its ``Job(job_id)`` has no equivalent of ``overwrite=True``, which is what makes
  every one of these routes re-pull the job's files from MinIO first. On
  Kubernetes the pod serving the request is usually not the pod that produced the
  file.
- Its picture route calls ``send_from_directory(f"work_dir/{job_id}", ...)``,
  a path relative to Flask's ``app.root_path`` (= ``cosmonaut_app/``), whereas this
  one passes the job's absolute working dir.

Above all it imports ``cosmo_suite.job.Job``, and the framework ``Job`` is still a
concrete job bound to ``cosmo_suite.db_manager``, not a contract — both are out of
slice 1. Revisit together with ``cosmonaut_job.py``.
"""

import io
import logging
import os
import zipfile

import dash_bootstrap_components as dbc
from flask import abort, send_file, send_from_directory

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.error_handling import JobNotFound

log = logging.getLogger(__name__)

DOWNLOAD_WORKDIR_ROUTE_TEMPLATE = "/download/<job_id>/work_dir.zip"


def _download_href(job_id):
    """Return the download URL for a job's work directory."""
    return f"/download/{job_id}/work_dir.zip"


def create_download_button(job_id, class_name="w-100 mt-2"):
    """Create a download button for a job's work directory."""
    return dbc.Button(
        "Download work_dir",
        color="primary",
        href=_download_href(job_id),
        external_link=True,
        className=class_name,
    )


def serve_files(app):
    """Serve static files from a directory."""

    @app.server.route("/pictures/<job_id>/<path:filename>")
    def serve_picture(job_id, filename):
        """Serve pictures."""
        log.debug(f"Serve picture {filename} for {job_id}")
        try:
            job = CosmonautJob(job_id=job_id, overwrite=True)
        except JobNotFound:
            log.error(f"Job not found for job_id={job_id}")
            abort(404, description="Job not found")

        picture_path = os.path.join(job.working_dir, filename)
        if not os.path.exists(picture_path):
            log.error(f"Picture not found at {picture_path}")
            abort(404, description="Picture not found")
        response = send_from_directory(job.working_dir, filename)

        # Add cache control headers to prevent browser caching
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    @app.server.route("/download/<job_id>/route.gpx")
    def download_gpx(job_id):
        """Serve GPX file for download."""
        log.debug(f"Serving GPX download for job_id={job_id}")

        try:
            job = CosmonautJob(job_id=job_id, overwrite=True)
        except JobNotFound:
            abort(404, description="Job not found")
        gpx_path = os.path.join(job.working_dir, "route.gpx")

        if not os.path.exists(gpx_path):
            log.error(f"GPX file not found at {gpx_path}")
            abort(404, description="GPX file not found")

        return send_file(
            gpx_path,
            mimetype="application/gpx+xml",
            as_attachment=True,
            download_name="route.gpx",
        )

    @app.server.route(DOWNLOAD_WORKDIR_ROUTE_TEMPLATE)
    def download_work_dir(job_id):
        """Download the entire work directory as a zip file.

        Security: job_id is validated via CosmonautJob() which queries the
        database (existence check). The working directory path is taken from
        the validated job object, never from user input.
        """
        log.debug(f"Download work dir for {job_id}")
        try:
            job = CosmonautJob(job_id=job_id, overwrite=True)
        except JobNotFound:
            abort(404, description="Job not found")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, _dirs, files in os.walk(job.working_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    arcname = os.path.relpath(file_path, job.working_dir)
                    zip_file.write(file_path, arcname)

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{job_id}.zip",
        )
