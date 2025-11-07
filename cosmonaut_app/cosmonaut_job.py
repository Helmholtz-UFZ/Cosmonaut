import logging
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
from cosmonaut_app.minio_manager import MiniIOManager

from cosmonaut_app.transformation import transform_csv
from cosmonaut_app.pydantic_models import JobModel
from sensor_routing.sensor_routing_cli import Config


class CosmonautJob:
    """
    This class represents a job submission by the user.

    It submits jobs to the PostgreSQL database,
    uploads the file to the MinIO object storage
    and can retrieve the job again.

    All business data is stored in self.model (JobModel instance).
    Filesystem paths are stored as direct instance attributes.
    """

    def __init__(self, job_id=None, download_from_minio=False):
        """Init class by id or make a new one."""
        if job_id is not None:
            logging.info(f"Load job with id {job_id}")
            if not DataBaseManager.check_existence(job_id):
                raise JobNotFound(job_id)
            self.load(job_id, download_from_minio)
        else:
            logging.info("Create new job")
            self._blank_job()

    def load(self, job_id, download_from_minio=False):
        """
        Get job information from the database,
        load the data from MinIO (if specified),
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

        # Download entire job directory from MinIO only if the flag is True
        if download_from_minio:
            minio_job_dir = f"{self.model.job_id}/"
            MiniIOManager.download_directory(minio_job_dir, self.working_dir)

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
        """Save the job to the database."""
        logging.info(f"Save job {self.model.job_id}")

        # Get all data from model
        data = self.model.model_dump(mode="json")

        # Separate Config fields from JobModel fields
        config_field_names = set(Config.model_fields.keys())

        # Extract config fields into separate dict
        config_data = {}
        for field_name in list(data.keys()):
            if field_name in config_field_names:
                config_data[field_name] = data.pop(field_name)

        # Add config as JSON field
        data["config"] = config_data

        # Save to database
        DataBaseManager.add_entry(data)

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
        config_field_names = set(Config.model_fields.keys())
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

    def delete(self):
        """Delete the job from the database and MinIO."""
        logging.debug(f"delete job {self.model.job_id}")
        # delete job from database
        DataBaseManager.delete_job(self.model.job_id)
        # delete files from MinIO
        MiniIOManager.delete_file(self.model.job_id)

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

        # Store information about the classification upload
        self.model.classification_upload = {
            "file_name": safe_name,
            "len": len(classification_data),
            "epsg": epsg_input,
        }
        self.save()
        return classification_data

    # TODO: Implement the submit method like John did it.
    def submit(self):
        """Submit the job."""
        self.model.submitted = True
        self.save()
        return self.model.job_id
