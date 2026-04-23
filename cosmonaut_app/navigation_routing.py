import io
import json
import logging
import os
from datetime import timedelta

import gpxpy
import qrcode
from pyproj import Transformer

from cosmonaut_app.config import get_download_url
from cosmonaut_app.object_storage_manager import get_presigned_download_url

log = logging.getLogger(__name__)


class RouteCreator:
    """Creates a GPX file and QR code from sensor-routing solution data."""

    def __init__(self, solution_path, working_dir, job_id, source_epsg):
        self.solution_path = solution_path
        self.working_dir = working_dir
        self.job_id = job_id
        self.source_epsg = source_epsg
        self.gpx_filename = "route.gpx"
        self.gpx_path = os.path.join(self.working_dir, self.gpx_filename)
        self.qr_code_filename = "qr_code.png"
        self.qr_code_path = os.path.join(self.working_dir, self.qr_code_filename)
        # Object key derived server-side from validated job_id — never pass user input here.
        object_key = f"{self.job_id}/{self.gpx_filename}"
        self.qr_code_url = get_presigned_download_url(
            object_key, expiry=timedelta(hours=24)
        )
        log.debug("RouteCreator initialized.")

    def create_gpx(self):
        """Creates a GPX file and QR code from the routing solution."""
        log.info("Starting GPX creation process.")
        if not os.path.exists(self.gpx_path):
            log.debug("Creating GPX file.")
            with open(self.solution_path, encoding="utf-8") as f:
                solution = json.load(f)

            gpx = gpxpy.gpx.GPX()
            gpx.name = f"Route ({solution['Optimization Objective']})"
            gpx.description = f"Distance: {solution['Distance']:.2f} km"

            gpx_track = gpxpy.gpx.GPXTrack()
            segment = gpxpy.gpx.GPXTrackSegment()

            transformer = Transformer.from_crs(self.source_epsg, 4326, always_xy=True)
            for x, y in solution["Path"]:
                lon, lat = transformer.transform(x, y)
                segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon))

            gpx_track.segments.append(segment)
            gpx.tracks.append(gpx_track)

            with open(self.gpx_path, "w", encoding="utf-8") as file:
                file.write(gpx.to_xml())
            log.debug(f"GPX file created at {self.gpx_path}.")
        self._create_qr_code()

        return self.qr_code_url

    def _create_qr_code(self):
        """Creates a QR code image based on the provided URL."""
        log.debug("Creating QR code.")
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.qr_code_url)
        qr.make(fit=True)

        img = qr.make_image(fill="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)

        with open(self.qr_code_path, "wb") as file:
            file.write(img_io.getvalue())

        log.debug(f"QR code created and saved at {self.qr_code_path}.")
