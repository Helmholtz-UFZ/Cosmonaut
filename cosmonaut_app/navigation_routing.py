import io
import os
import logging
import json

import gpxpy
import qrcode

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class RouteCreator:
    """Creates a GPX file and QR code from GeoJSON route data."""

    def __init__(self, geojson_path, output_dir):
        self.geojson_path = geojson_path
        self.output_dir = output_dir
        self.gpx_filename = "route.gpx"
        self.gpx_path = os.path.join(self.output_dir, self.gpx_filename)
        # TODO set proper URL base in config
        # This must be switched to the production URL when deployed
        # URL_BASE = "https://cosmonaut.web-intern-stage.app.ufz.de"
        URL_BASE = "http://localhost:8080"
        self.qr_code_filename = "qr_code.png"
        self.qr_code_path = os.path.join(self.output_dir, self.qr_code_filename)
        self.qr_code_url = f"{URL_BASE}/downloads/{self.gpx_filename}"
        logger.debug("RouteCreator initialized.")

    def create_gpx(self):
        """Creates debuga GPX file and QR code based on the provided GeoJSON data."""
        if os.path.exists(self.qr_code_path):
            logger.info("GPX file already exists. Skipping creation.")
            return self.qr_code_url
        logger.debug("Creating GPX file.")
        with open(self.geojson_path, encoding="utf-8") as f:
            geojson_data = json.load(f)
        gpx = gpxpy.gpx.GPX()

        # Add metadata to GPX
        metadata = geojson_data["metadata"]
        gpx.name = metadata.get("Optimization Objective", "Route")
        gpx.description = f"Distance: {metadata.get('Distance', 'N/A')} km, Benefit: {metadata.get('Benefit', 'N/A')}"  # noqa

        # Create a single track
        gpx_track = gpxpy.gpx.GPXTrack()

        # Handle segments based on features like "slow"
        slow_segments = metadata.get("slow", [])
        current_segment = gpxpy.gpx.GPXTrackSegment()

        for i, feature in enumerate(self.geojson_data["features"]):
            for coordinate in feature["geometry"]["coordinates"]:
                point = gpxpy.gpx.GPXTrackPoint(coordinate[1], coordinate[0])
                current_segment.points.append(point)

            # Check if the current segment should end
            if any(start <= i <= end for start, end in slow_segments):
                gpx_track.segments.append(current_segment)
                current_segment = gpxpy.gpx.GPXTrackSegment()

        # Append the last segment
        if current_segment.points:
            gpx_track.segments.append(current_segment)

        gpx.tracks.append(gpx_track)

        # Save the GPX file
        with open(self.gpx_path, "w", encoding="utf-8") as file:
            file.write(gpx.to_xml())
        logger.debug(f"GPX file created at {self.gpx_path}.")
        self._create_qr_code()

        return self.qr_code_url

    def _create_qr_code(self):
        """Creates a QR code image based on the provided URL."""
        logger.debug("Creating QR code.")
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

        logger.debug(f"QR code created and saved at {self.qr_code_path}.")
