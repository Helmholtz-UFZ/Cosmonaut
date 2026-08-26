"""Serve files from a directory.

The generic routes — pictures and the work_dir zip — come from
``cosmo_suite.files_route.serve_files``, which since v0.6.1 takes the app's own
job class. Only the GPX route stays here: it is the target of the QR code and the
completion mail, and the framework has no counterpart for a domain file path.

``create_download_button`` is re-exported from the framework so the button and
the route it links to cannot drift apart — they are now defined in one place.
"""

import logging
import os

from cosmo_suite.files_route import create_download_button as create_download_button
from cosmo_suite.files_route import serve_files as _serve_framework_files
from flask import abort, send_file

from cosmonaut_app.constants.general import GPX_FILE
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.error_handling import JobNotFound

log = logging.getLogger(__name__)


class ServedJob(CosmonautJob):
    """The job class the file routes construct, adapting two app behaviours.

    ``overwrite=True``: constructing a job re-pulls its files from object
    storage. On Kubernetes the pod serving a download is usually not the pod that
    produced the file, and the default ``--ignore-existing`` would keep a stale
    local copy — which is exactly what happens after a route is regenerated with
    the reverse-route toggle.

    ``abort(404)``: an unknown job id is a not-found, not a server error. The
    framework's routes let ``JobNotFound`` propagate, which Flask turns into a
    500; raising the HTTP exception here keeps the 404 without the framework
    needing to know about it.
    """

    def __init__(self, job_id):
        """Load the job, refreshing its files, or answer 404."""
        try:
            super().__init__(job_id=job_id, overwrite=True)
        except JobNotFound:
            log.error(f"Job not found for job_id={job_id}")
            abort(404, description="Job not found")


def serve_files(app):
    """Register the framework's file routes plus cosmonaut's GPX route."""
    _serve_framework_files(app, job_class=ServedJob)

    @app.server.route(f"/download/<job_id>/{GPX_FILE}")
    def download_gpx(job_id):
        """Serve GPX file for download."""
        log.debug(f"Serving GPX download for job_id={job_id}")

        job = ServedJob(job_id)
        gpx_path = os.path.join(job.working_dir, GPX_FILE)

        if not os.path.exists(gpx_path):
            log.error(f"GPX file not found at {gpx_path}")
            abort(404, description="GPX file not found")

        return send_file(
            gpx_path,
            mimetype="application/gpx+xml",
            as_attachment=True,
            download_name=GPX_FILE,
        )
