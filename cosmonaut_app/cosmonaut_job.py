import base64
import csv
import glob
import json
import logging
import math
import os
import uuid
from datetime import date, timedelta

import pandas as pd
from pyproj import CRS, Transformer
from sensor_routing.constants import (
    MEMBERSHIP_FILENAME,
    OSM_FILENAME,
    PREDICTOR_FILENAME,
    ROUTE_FILENAME,
)
from sensor_routing.full_pipeline_cli import (
    parse_membership_file,
    parse_predictor_file,
    validate_predictor_membership_consistency,
)

from cosmonaut_app.config import (
    DAYS_DELETE_NOT_SUBMITTED,
    DAYS_DELETE_SUBMITTED,
    WEB_WORK_DIR,
)
from cosmonaut_app.constants.general import (
    GPX_FILE,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    LOG_FILE_NAME,
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    QR_CODE_FILE,
    STREET_EDITS_FILE,
)
from cosmonaut_app.background_job_manager import background_job_manager
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.error_handling import FileValidationError
from cosmonaut_app.navigation_routing import RouteCreator
from cosmonaut_app.object_storage_manager import (
    delete_directory_from_storage,
    get_files,
    save_files,
)
from cosmonaut_app.pydantic_models import FullPipelineConfig, JobModel


def _transform_csv(input_file, epsg_input, epsg_output):
    """Transform coordinates in a CSV file from one CRS to another.

    Args:
        input_file: Path to the input CSV file.
        epsg_input: EPSG code of the input CRS.
        epsg_output: EPSG code of the output CRS.

    Returns:
        DataFrame with transformed coordinates.
    """
    logging.info(f"Starting transformation of CSV file: {input_file}")

    if not input_file.endswith((".csv", ".txt")):
        logging.error("Input file must be a CSV or TXT file.")
        raise ValueError("Input file must be a CSV file.")

    with open(input_file, "r") as csvfile:
        sample = csvfile.read(4096)
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
        delimiter = dialect.delimiter

    crs_input = CRS.from_epsg(epsg_input)
    crs_output = CRS.from_epsg(epsg_output)
    transformer = Transformer.from_crs(crs_input, crs_output)

    df = pd.read_csv(input_file, delimiter=delimiter, header=0 if has_header else None)

    if not has_header:
        df.columns = [f"col_{i}" for i in range(len(df.columns))]

    potential_coord_cols = []
    for col in df.columns:
        if df[col].dtype.kind in "iuf":
            if (df[col].min() < 0 or df[col].max() > 1) and len(df[col].unique()) > 10:
                potential_coord_cols.append(col)

    if len(potential_coord_cols) == 2:
        x_col, y_col = potential_coord_cols
    elif has_header:
        x_candidates = [
            col
            for col in df.columns
            if any(term in col.lower() for term in ["east", "long", "x", "lon"])
        ]
        y_candidates = [
            col
            for col in df.columns
            if any(term in col.lower() for term in ["north", "lat", "y"])
        ]

        if len(x_candidates) > 0 and len(y_candidates) > 0:
            x_col = x_candidates[0]
            y_col = y_candidates[0]
        else:
            raise ValueError("Could not automatically identify coordinate columns.")
    else:
        raise ValueError("Could not automatically identify coordinate columns.")

    df["Latitude"], df["Longitude"] = transformer.transform(
        df[x_col].values, df[y_col].values
    )

    df.drop([x_col, y_col], axis=1, inplace=True)

    return df


def _get_bounds(classification_df):
    """Calculate the rectangular bounds of the given points.

    Returns:
        A list containing [[min_lat, min_lon], [max_lat, max_lon]].
    """
    lon = classification_df.Longitude
    lat = classification_df.Latitude

    min_lon, max_lon = lon.min(), lon.max()
    min_lat, max_lat = lat.min(), lat.max()

    return [[min_lat, min_lon], [max_lat, max_lon]]


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
        self.model.start_date = date.today()
        self._create_working_dir()

        self.save()

    def _create_working_dir(self):
        """Create the working directory for the job."""
        self.working_dir = os.path.join(WEB_WORK_DIR, self.model.job_id)
        os.makedirs(self.working_dir, exist_ok=True)

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
        Dump routing parameters (Config fields) to parameters.json in working directory.

        Extracts only the fields from the Config model and writes them to
        a JSON file in the working directory.
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

        # Write to parameters.json in working directory
        parameters_file = os.path.join(self.working_dir, "parameters.json")
        with open(parameters_file, "w") as f:
            json.dump(config_data, f, indent=2)

        logging.debug(f"Routing parameters written to {parameters_file}")

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

    def upload_membership(self, file_name, content, epsg_input):
        """Upload and process membership CSV file."""
        logging.info(f"Upload membership file {file_name} with EPSG {epsg_input}")

        # Remove previous membership file if it exists
        previous_file = self.model.membership_upload["file_name"]
        previous_file_path = os.path.join(self.working_dir, previous_file)
        if os.path.exists(previous_file_path):
            os.remove(previous_file_path)
            logging.info(f"Removed previous membership file {previous_file}")

        _content_type, content_string = content.split(",", 1)
        decoded = base64.b64decode(content_string)

        # Save with canonical name for sensor_routing pipeline
        file_path = os.path.join(self.working_dir, MEMBERSHIP_FILENAME)

        with open(file_path, "wb") as f:
            f.write(decoded)

        # Validate with sensor_routing parser
        try:
            membership_df = parse_membership_file(file_path)
        except Exception as e:
            logging.info(f"Membership file validation failed: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        try:
            classification_data = _transform_csv(file_path, epsg_input, 4326)
        except ValueError as e:
            logging.info(f"Error transforming CSV file: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        # Calculate bounds, position, and zoom
        bounds = _get_bounds(classification_data)
        position, zoom = self._calculate_map_position_from_bounds(bounds)

        # Store EPSG as model attribute
        self.model.epsg = epsg_input

        # Store information about the membership upload
        self.model.membership_upload = {
            "file_name": MEMBERSHIP_FILENAME,
            "len": len(classification_data),
            "center": position,
            "zoom": zoom,
            "bounds": bounds,
        }
        self.save()
        logging.debug("Finished uploading and processing membership file")
        return file_path, bounds, membership_df

    def upload_predictor(self, content):
        """Upload and validate predictor CSV file."""
        logging.info(f"Upload predictor file for job {self.model.job_id}")

        _content_type, content_string = content.split(",", 1)
        decoded = base64.b64decode(content_string)

        # Save with canonical name for sensor_routing pipeline
        file_path = os.path.join(self.working_dir, PREDICTOR_FILENAME)

        with open(file_path, "wb") as f:
            f.write(decoded)

        # Validate with sensor_routing parser
        try:
            parse_predictor_file(file_path)
        except Exception as e:
            logging.info(f"Predictor file validation failed: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        # Cross-validate with membership file
        membership_path = os.path.join(self.working_dir, MEMBERSHIP_FILENAME)
        try:
            validate_predictor_membership_consistency(file_path, membership_path)
        except Exception as e:
            logging.info(f"Predictor-membership consistency check failed: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        self.model.predictor_upload = {
            "file_name": PREDICTOR_FILENAME,
            "len": len(decoded),
        }
        self.save()
        logging.debug("Finished uploading and processing predictor file")

    def delete_predictor(self):
        """Delete predictor file and reset predictor_upload."""
        logging.info(f"Deleting predictor data for job {self.model.job_id}")

        file_path = os.path.join(self.working_dir, PREDICTOR_FILENAME)
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.debug(f"Deleted predictor file: {file_path}")

        default_predictor_upload = JobModel.model_fields["predictor_upload"].default
        self.model.predictor_upload = default_predictor_upload.copy()
        self.save()

        logging.info(f"Predictor data deleted for job {self.model.job_id}")

    def get_street_processing_status(self):
        """Get street processing status, syncing from Celery if task is running.

        Returns:
            str: "PENDING", "RUNNING", "COMPLETED", or "FAILED"
        """
        sp = self.model.membership_upload["street_processing"]
        if sp in ("PENDING", "COMPLETED", "FAILED"):
            return sp
        # sp is a Celery task ID — check its status
        celery_info = background_job_manager.get_job_status(sp)
        celery_status = celery_info["status"]
        if celery_status == "SUCCESS":
            self.model.membership_upload["street_processing"] = "COMPLETED"
            self.save()
            return "COMPLETED"
        elif celery_status in ("FAILURE", "REVOKED"):
            self.model.membership_upload["street_processing"] = "FAILED"
            self.save()
            return "FAILED"
        return "RUNNING"

    def delete_membership(self):
        """Delete membership file, predictor, OSM files, plots and reset state."""
        logging.info(f"Deleting membership data for job {self.model.job_id}")

        # Revoke running upload task if street_processing holds a task ID
        sp = self.model.membership_upload["street_processing"]
        if sp not in ("PENDING", "COMPLETED", "FAILED"):
            background_job_manager.revoke_job(sp, terminate=True)
            logging.info(
                f"Revoked upload processing task {sp} for job {self.model.job_id}"
            )

        # Cascade: delete predictor first
        self.delete_predictor()

        # Delete membership CSV file
        membership_path = os.path.join(self.working_dir, MEMBERSHIP_FILENAME)
        if os.path.exists(membership_path):
            os.remove(membership_path)
            logging.debug(f"Deleted membership file: {membership_path}")

        # Delete OSM data files
        for osm_name in [
            OSM_DATA_DOWNLOAD_FILE,
            OSM_DATA_EDITED_FILE,
            OSM_FILENAME,
            STREET_EDITS_FILE,
        ]:
            osm_path = os.path.join(self.working_dir, osm_name)
            if os.path.exists(osm_path):
                os.remove(osm_path)
                logging.debug(f"Deleted OSM file: {osm_path}")

        # Delete plot files (new name + legacy names)
        for plot_file in glob.glob(os.path.join(self.working_dir, "*_output*.tif")):
            os.remove(plot_file)
            logging.debug(f"Deleted plot file: {plot_file}")
        membership_tif = os.path.join(self.working_dir, "membership.tif")
        if os.path.exists(membership_tif):
            os.remove(membership_tif)
            logging.debug(f"Deleted plot file: {membership_tif}")

        # Reset membership_upload to default values
        default_membership_upload = JobModel.model_fields["membership_upload"].default
        self.model.membership_upload = default_membership_upload.copy()

        self.save()

        logging.info(f"Membership data deleted for job {self.model.job_id}")

    def create_qr_code_routing(self):
        logging.info(f"Creating QR code for routing job {self.model.job_id}")
        geojson_path = os.path.join(self.working_dir, ROUTE_FILENAME)

        route_creator = RouteCreator(
            geojson_path=geojson_path,
            working_dir=self.working_dir,
            job_id=self.model.job_id,
        )
        qr_code_url = route_creator.create_gpx()
        self.save()
        return qr_code_url

    def get_route_polyline(self):
        """Return the route as WGS84 [[lat, lon], ...] positions, or None if unavailable."""
        route_path = os.path.join(self.working_dir, ROUTE_FILENAME)
        if not os.path.exists(route_path):
            return None
        with open(route_path) as f:
            solution = json.load(f)
        transformer = Transformer.from_crs(self.model.epsg, 4326, always_xy=True)
        positions = []
        for x, y in solution["Path"]:
            lon, lat = transformer.transform(x, y)
            positions.append([lat, lon])
        return positions

    def submit(self):
        """Submit the job to background worker."""
        logging.info(f"Submitting job {self.model.job_id} to background worker")
        try:
            # Mark as submitted and set status to RUNNING
            self.model.submitted = True
            self.model.status = JOB_STATUS_RUNNING
            self.save()  # This calls dump_routing_params() automatically

            celery_task_id, failed = background_job_manager.submit_routing_job(self)

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
            logging.error(f"Failed to submit job {self.model.job_id}: {str(e)}")
            raise

    def get_status(self) -> str:
        """Get current job status, syncing from Celery if terminated.

        If job has a Celery task and is currently RUNNING, checks Celery state
        and updates database status if task has terminated (SUCCESS/FAILURE).

        Returns:
            str: Current job status (PENDING, RUNNING, COMPLETED, or FAILED)
        """
        # Only sync if job has a celery task and is currently RUNNING
        if self.model.celery_task_id and self.model.status == JOB_STATUS_RUNNING:
            # Query Celery for task status
            celery_status_info = background_job_manager.get_job_status(
                self.model.celery_task_id
            )
            celery_status = celery_status_info["status"]

            # Map Celery states to job statuses
            if celery_status == "SUCCESS":
                self.model.status = JOB_STATUS_COMPLETED
                self.save()
                logging.info(f"Synced job {self.model.job_id} status to COMPLETED")
            elif celery_status in ["FAILURE", "REVOKED"]:
                self.model.status = JOB_STATUS_FAILED
                self.save()
                logging.warning(
                    f"Synced job {self.model.job_id} status to FAILED "
                    f"(Celery: {celery_status})"
                )

        return self.model.status

    def time_to_live(self) -> int:
        """Return number of days until this job is deleted by cleanup."""
        if self.model.submitted:
            retention_days = DAYS_DELETE_SUBMITTED
        else:
            retention_days = DAYS_DELETE_NOT_SUBMITTED
        deletion_date = self.model.start_date + timedelta(days=retention_days)
        return (deletion_date - date.today()).days

    def get_logs(self) -> str:
        """Retrieve logs for the job from object storage.

        Returns:
            str: Job logs as a string
        """
        logging.info(f"Retrieving logs for job {self.model.job_id}")
        log_file_path = os.path.join(self.working_dir, LOG_FILE_NAME)
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as f:
                log_content = f.read()
            if not log_content.strip():
                log_content = "Logs empty."
        else:
            log_content = "No log file found."

        return log_content

    def reset(self):
        """Reset job to PENDING state by clearing output files and task state.

        This method:
        - Cancels the Celery task if job is currently RUNNING
        - Deletes output files (logs, solutions, GPX, QR codes)
        - Preserves input files (uploaded data, parameters, OSM data, plots)
        - Sets status to PENDING
        - Clears celery_task_id and submitted flag
        - Saves changes to database and object storage
        """
        logging.info(f"Resetting job {self.model.job_id}")

        # If job is currently running, cancel the Celery task first
        if self.model.status == JOB_STATUS_RUNNING and self.model.celery_task_id:
            logging.info(f"Cancelling running task {self.model.celery_task_id}")
            background_job_manager.revoke_job(self.model.celery_task_id, terminate=True)

        # Delete known output files
        output_files = [LOG_FILE_NAME, ROUTE_FILENAME, GPX_FILE, QR_CODE_FILE]
        for fname in output_files:
            fpath = os.path.join(self.working_dir, fname)
            if os.path.isfile(fpath):
                os.unlink(fpath)
                logging.debug(f"Deleted output file: {fpath}")

        # Reset job state
        self.model.status = JOB_STATUS_PENDING
        self.model.celery_task_id = None
        self.model.submitted = False

        # Save changes
        self.save()

        logging.info(f"Job {self.model.job_id} reset to PENDING")
