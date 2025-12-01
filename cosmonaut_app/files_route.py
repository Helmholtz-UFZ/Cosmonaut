"""Serve files from a directory."""

import logging

from flask import send_from_directory
from cosmonaut_app.cosmonaut_job import CosmonautJob


def serve_files(app):
    """Serve static files from a directory."""

    @app.server.route("/pictures/<job_id>/<path:filename>")
    def serve_file(job_id, filename):
        """Serve pictures."""
        logging.debug(f"Serve file {filename} for {job_id}", extra={"tag": "frontend"})
        # Assure that the job exists and all files are ready
        job = CosmonautJob(job_id)

        response = send_from_directory(job.output_dir, filename)

        # Add cache control headers to prevent browser caching
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response
