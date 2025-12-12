import logging
import math
import os
import uuid
from datetime import date
import base64
import json
from werkzeug.utils import secure_filename
from cosmonaut_app.config import (
    DAYS_DELETE_NOT_SUBMITTED,
    DAYS_DELETE_SUBMITTED,
    WEB_WORK_DIR,
)
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.object_storage_manager import (
    get_files,
    save_files,
    delete_directory_from_storage,
)
from cosmonaut_app.navigation_routing import RouteCreator
from cosmonaut_app.transformation import get_bounds, transform_csv
from cosmonaut_app.pydantic_models import JobModel, FullPipelineConfig


class CosmonautJob:
    """
    This class represents a job submission by the user.

    It submits jobs to the PostgreSQL database,
    uploads the file to the MinIO object storage
    and can retrieve the job again.

    All business data is stored in self.model (JobModel instance).
    Filesystem paths are stored as direct instance attributes.
    """

    def __init__(self, job_id=None):
        """Init class by id or make a new one."""
        if job_id is not None:
            logging.info(f"Load job with id {job_id}")
            if not DataBaseManager.check_existence(job_id):
                raise JobNotFound(job_id)
            self.load(job_id)
        else:
            logging.info("Create new job")
            self._blank_job()

    def load(self, job_id):
        """
        Get job information from the database,
        load the data from object storage,
        and store files in the working directory.
        """
        logging.debug(f"load job with id {job_id}")

        # Get job information from the database
        job_data = DataBaseManager.get_job_columns(job_id)

        # Extract config JSON and merge back into job_data
        config_data = job_data.pop("config", {})
        if config_data:
            job_data.update(config_data)

        # Instantiate model with all fields
        self.model = JobModel(**job_data)

        # Set up filesystem paths
        self._create_working_dir()

        # Always download files from object storage when loading existing job
        get_files(self.model.job_id)

    def _blank_job(self):
        """Create a new job with a unique ID."""
        self.model = JobModel()  # Initialize with defaults
        while True:
            job_id = str(uuid.uuid4())[:8]
            if not DataBaseManager.check_existence(job_id):
                break

        self.model.job_id = job_id
        self._create_working_dir()

        self.save()

    def _create_working_dir(self):
        """Create the working directory for the job."""
        self.working_dir = os.path.join(WEB_WORK_DIR, self.model.job_id)
        os.makedirs(self.working_dir, exist_ok=True)
        self.input_dir = os.path.join(self.working_dir, "input")
        os.makedirs(self.input_dir, exist_ok=True)
        self.plots_dir = os.path.join(self.working_dir, "plots")
        os.makedirs(self.plots_dir, exist_ok=True)
        self.output_dir = os.path.join(self.working_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def save(self):
        """Save the job to the database and sync files to object storage."""
        logging.info(f"Save job {self.model.job_id}")

        # Get all data from model
        data = self.model.model_dump(mode="json")

        # Separate Config fields from JobModel fields
        config_field_names = set(FullPipelineConfig.model_fields.keys())

        # Extract config fields into separate dict
        config_data = {}
        for field_name in list(data.keys()):
            if field_name in config_field_names:
                config_data[field_name] = data.pop(field_name)

        # Add config as JSON field
        data["config"] = config_data

        # Save to database
        DataBaseManager.add_entry(data)

        self.dump_routing_params()

        # Auto-sync files to object storage
        save_files(self.model.job_id)

    def dump_routing_params(self):
        """
        Dump routing parameters (Config fields) to parameters.json in input directory.

        Extracts only the fields from the Config model and writes them to
        a JSON file in the input work directory.
        """
        logging.info(f"Dumping routing parameters for job {self.model.job_id}")

        # Get all data from model
        data = self.model.model_dump(mode="json")

        # Extract only Config fields
        config_field_names = set(FullPipelineConfig.model_fields.keys())
        config_data = {
            field_name: data[field_name]
            for field_name in data.keys()
            if field_name in config_field_names
        }

        # Write to parameters.json in input directory
        parameters_file = os.path.join(self.input_dir, "parameters.json")
        with open(parameters_file, "w") as f:
            json.dump(config_data, f, indent=2)

        logging.info(f"Routing parameters written to {parameters_file}")

    def _calculate_map_position_from_bounds(self, bounds):
        """
        Calculate center position and zoom level from bounds.

        Args:
            bounds: [[min_lat, min_lon], [max_lat, max_lon]]

        Returns:
            tuple: (position [lat, lon], zoom level)
        """
        min_lat, min_lon = bounds[0]
        max_lat, max_lon = bounds[1]

        # Calculate center
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        position = [center_lat, center_lon]

        # Calculate zoom level
        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon

        # Leaflet zoom calculation: fit the larger dimension
        # Each zoom level doubles the map scale
        # At zoom 0, the world is 256 pixels wide
        # World width in degrees is 360, height is ~170 (Web Mercator)
        lat_zoom = math.log2(170 * 800 / (lat_diff * 256)) if lat_diff > 0 else 15
        lon_zoom = math.log2(360 * 1000 / (lon_diff * 256)) if lon_diff > 0 else 15

        # Use the smaller zoom to ensure everything fits
        zoom = int(min(lat_zoom, lon_zoom, 18))  # Cap at zoom 18

        # Ensure minimum zoom of 5
        zoom = max(5, zoom)

        return position, zoom

    def delete(self):
        """Delete the job from the database and object storage."""
        logging.debug(f"delete job {self.model.job_id}")
        # delete job from database
        DataBaseManager.delete_job(self.model.job_id)
        # delete files from object storage
        delete_directory_from_storage(self.model.job_id)

    def time_to_life(self):
        """Return the time to life of the job."""
        # Note: start_date was removed from the model
        # This method needs to be reimplemented if needed
        days_passed = (date.today() - self.start_date).days
        if not self.model.submitted:
            return DAYS_DELETE_SUBMITTED - days_passed
        else:
            return DAYS_DELETE_NOT_SUBMITTED - days_passed

    def upload_file(self, file_name, content, epsg_input):
        """Upload and process classification CSV file."""
        logging.info(f"Upload classification file {file_name} with EPSG {epsg_input}")

        # Check if previously a file was uploaded and remove it
        previous_file = self.model.classification_upload.get("file_name")
        previous_file_path = os.path.join(self.input_dir, previous_file)
        if os.path.exists(previous_file_path):
            os.remove(previous_file_path)
            logging.info(f"Removed previous classification file {previous_file}")

        _content_type, content_string = content.split(",", 1)
        decoded = base64.b64decode(content_string)

        safe_name = secure_filename(file_name)
        file_path = os.path.join(self.input_dir, safe_name)

        with open(file_path, "wb") as f:
            f.write(decoded)

        try:
            classification_data = transform_csv(file_path, epsg_input, 4326)
        except ValueError as e:
            logging.info(f"Error transforming CSV file: {e}")
            os.remove(file_path)
            raise e

        # Calculate bounds, position, and zoom
        bounds = get_bounds(classification_data)
        position, zoom = self._calculate_map_position_from_bounds(bounds)

        # Store EPSG as model attribute
        self.model.epsg = epsg_input

        # Store information about the classification upload
        self.model.classification_upload = {
            "file_name": safe_name,
            "len": len(classification_data),
            "center": position,
            "zoom": zoom,
        }
        self.save()
        return classification_data, file_path, bounds

    def create_qr_code_routing(self):
        # TODO the name "solution_transformed.json" should be abstracted somewhere. Who
        # is responsible for writing it?
        geojson_path = os.path.join(self.output_dir, "solution_transformed.json")

        route_creator = RouteCreator(geojson_path, self.output_dir)
        qr_code_url = route_creator.create_gpx()
        self.save()
        return qr_code_url

    def submit(self):
        """Submit the job to background worker."""
        try:
            # Lazy import to avoid circular imports
            from cosmonaut_app.background_job_manager import get_background_job_manager

            # Mark as submitted and save (this will dump routing params via save())
            self.model.submitted = True
            self.save()  # This calls dump_routing_params() automatically

            # Get the singleton manager and submit the job
            job_manager = get_background_job_manager()
            celery_task_id, failed = job_manager.submit_routing_job(self)

            if failed:
                logging.error(f"Failed to submit job {self.model.job_id}")
                return None

            # Store task ID and save again
            self.model.celery_task_id = celery_task_id
            self.save()

            logging.info(
                f"Job {self.model.job_id} submitted with task_id={celery_task_id}"
            )
            return celery_task_id

        except Exception as e:
            # Fail hard per user preference - no graceful fallback
            logging.error(f"Failed to submit job {self.model.job_id}: {str(e)}")
            raise
