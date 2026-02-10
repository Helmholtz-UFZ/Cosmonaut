"""Serve files from a directory."""

import logging
import os

from flask import send_from_directory, send_file, abort
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.error_handling import JobNotFound


def serve_files(app):
    """Serve static files from a directory."""

    @app.server.route("/pictures/<job_id>/<path:filename>")
    def serve_picture(job_id, filename):
        """Serve pictures."""
        logging.debug(f"Serve picture {filename} for {job_id}")
        try:
            job = CosmonautJob(job_id=job_id)
        except JobNotFound:
            logging.error(f"Job not found for job_id={job_id}")
            abort(404, description="Job not found")

        picture_path = os.path.join(job.working_dir, filename)
        if not os.path.exists(picture_path):
            logging.error(f"Picture not found at {picture_path}")
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
        logging.debug(f"Serving GPX download for job_id={job_id}")

        try:
            job = CosmonautJob(job_id=job_id)
        except JobNotFound:
            abort(404, description="Job not found")
        gpx_path = os.path.join(job.working_dir, "route.gpx")

        if not os.path.exists(gpx_path):
            logging.error(f"GPX file not found at {gpx_path}")
            abort(404, description="GPX file not found")

        return send_file(
            gpx_path,
            mimetype="application/gpx+xml",
            as_attachment=True,
            download_name="route.gpx",
        )
