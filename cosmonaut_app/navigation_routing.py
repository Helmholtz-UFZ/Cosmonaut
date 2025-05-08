import base64
import io
import os
import logging

import gpxpy
import qrcode
from cosmonaut_app.minio_manager import MiniIOManager

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class RouteCreator:
    """
    A class that creates routes and performs various operations on them.

    Args:
        geojson_data (dict): The GeoJSON data containing the route.

    Attributes:
        geojson_data (dict): The GeoJSON data loaded from the file.

    Methods:
        create_gpx: Creates a GPX file based on the provided GeoJSON data.
        upload_gpx: Uploads the specified GPX file and returns the link.
        create_qr_code: Creates a QR code image based on the provided URL.
    """

    def __init__(self, geojson_data):
        self.geojson_data = geojson_data
        logger.info("RouteCreator initialized with GeoJSON data.")

    def create_gpx(self, filename="route.gpx", path="."):
        """
        Creates a GPX file based on the provided GeoJSON data.

        Args:
            filename (str, optional): The name of the GPX file to be created.
                Defaults to "route.gpx".
            path (str, optional): The path where the GPX file will be saved.
                Defaults to the current directory.
        """
        logger.info("Creating GPX file.")
        gpx = gpxpy.gpx.GPX()

        # Add metadata to GPX
        metadata = self.geojson_data.get("metadata", {})
        gpx.name = metadata.get("Optimization Objective", "Route")
        gpx.description = f"Distance: {metadata.get('Distance', 'N/A')} km, Benefit: {metadata.get('Benefit', 'N/A')}"

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
        full_path = os.path.join(path, filename)
        with open(full_path, "w") as file:
            file.write(gpx.to_xml())
        logger.info(f"GPX file created at {full_path}.")

    def upload_gpx(self, filename="route.gpx", job_id=None):
        """
        Uploads the specified GPX file to MinIO and returns the link.

        Args:
            filename (str, optional): The name of the GPX file to be uploaded.
                Defaults to "route.gpx".
            job_id (str, optional): The job ID for the MinIO path.

        Returns:
            str: The link to the uploaded GPX file.
        """
        logger.info("Uploading GPX file to MinIO.")
        minio_manager = MiniIOManager("cosmic-routing")
        file_path = os.path.join("cosmonaut_app/work_dir", job_id, "output", filename)
        minio_manager.upload_file(file_path, f"{job_id}/output/{filename}")
        minio_manager.make_file_public(f"{job_id}/output/{filename}")
        url = minio_manager.get_file_url(f"{job_id}/output/{filename}")
        logger.info(f"GPX file uploaded to MinIO. URL: {url}")
        return url

    def create_qr_code(self, url, filename="qr_code.png", path="."):
        """
        Creates a QR code image based on the provided URL.

        Args:
            url (str): The URL to be encoded in the QR code.
            filename (str, optional): The name of the QR code image file.
                Defaults to "qr_code.png".
            path (str, optional): The path where the QR code image will be saved.
                Defaults to the current directory.

        Returns:
            dict: A dictionary containing the URL and the base64-encoded data URI of the QR code image.
        """
        logger.info("Creating QR code.")
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)
        img_data = base64.b64encode(img_io.getvalue()).decode()

        full_path = os.path.join(path, filename)
        with open(full_path, "wb") as file:
            file.write(img_io.getvalue())
        logger.info(f"QR code created and saved at {full_path}.")

        return {"url": url, "qr_code": f"data:image/png;base64,{img_data}"}
