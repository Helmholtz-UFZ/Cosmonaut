import logging
import os
import uuid
from datetime import date

from cosmonaut_app.config import (
    DAYS_DELETE_NOT_SUBMITTED,
    DAYS_DELETE_SUBMITTED,
    WEB_WORK_DIR,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.minio_manager import MiniIOManager


def get_attributes(clazz):
    """Retrieve a list of non-method attributes of a class."""
    return [
        name
        for name, attr in clazz.__dict__.items()
        if not name.startswith("__")
        and not callable(attr)
        and not isinstance(attr, staticmethod)
    ]


class CosmonautJob:
    """
    This class represents a job submission by the user.

    It submits jobs to the PostgreSQL database,
    uploads the file to the MinIO object storage
    and can retrieve the job again.
    """

    job_id = None
    start_date = None
    end_date = None
    data_uploaded = None
    submitted = None
    email = None
    notified_end = None
    stage = None
    status = None
    version = None
    file_names = []
    selected_road_tags = []

    def __init__(
        self, job_id=None, base_work_dir=WEB_WORK_DIR, download_from_minio=False
    ):
        """Init class by id or make a new one."""
        self.base_work_dir = base_work_dir
        if job_id is not None:
            logging.debug(f"load job with id {job_id}")
            self.job_id = job_id  # Set job_id to the instance variable
            self.load(download_from_minio)  # Pass the flag to control MinIO downloads
        else:
            logging.debug("create new job")
            self._blank_job()

    def load(self, download_from_minio=False):
        """
        Get job information from the database,
        load the data from MinIO (if specified),
        and store files in the working directory.
        """
        logging.debug(f"load job with id {self.job_id}")

        # Get job information from the database
        job_data = DataBaseManager.get_job_columns(self.job_id)
        for name, value in job_data.items():
            logging.info(f"Set attribute {name} to {value}")
            if name in [
                "job_id",
                "start_date",
                "end_date",
                "stage",
                "submitted",
                "email",
                "data_uploaded",
            ]:
                setattr(self, name, value)
            else:
                logging.warning(f"Unknown attribute {name} found in database")

        # Recreate the working directory
        working_dir = os.path.join(self.base_work_dir, self.job_id)
        if not os.path.exists(working_dir):
            logging.info(
                f"Create working directory {working_dir} for job {self.job_id}"
            )
            os.makedirs(working_dir)

        # Download entire job directory from MinIO only if the flag is True
        if download_from_minio:
            minio_job_dir = f"{self.job_id}/"
            MiniIOManager.download_directory(minio_job_dir, working_dir)

    def _blank_job(self):
        """Create a new job."""
        while True:
            job_id = str(uuid.uuid4())[:8]
            if DataBaseManager.check_existence(self.job_id):
                logging.debug(f"job_id {job_id} already exists")
                continue
            break
        self.job_id = job_id
        self.start_date = date.today()
        self.submitted = False
        self.status = "created"
        self.stage = 0

    def save(self):
        """Save the job to the database."""
        logging.debug(f"save job {self.job_id}")
        # save job to database
        DataBaseManager.add_entry(
            {
                "job_id": self.job_id,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "status": self.status,
                "submitted": self.submitted,
                "email": self.email,
                "stage": self.stage,
                "file_names": ",".join(self.file_names),
            }
        )

    def delete(self):
        """Delete the job from the database and MinIO."""
        logging.debug(f"delete job {self.job_id}")
        # delete job from database
        DataBaseManager.delete_job(self.job_id)
        # delete files from MinIO
        MiniIOManager.delete_file(self.job_id)

    def time_to_life(self):
        """Return the time to life of the job."""
        days_passed = (date.today() - self.start_date).days
        if not self.submitted:
            return DAYS_DELETE_SUBMITTED - days_passed
        else:
            return DAYS_DELETE_NOT_SUBMITTED - days_passed

    # TODO: Implement the submit method like John did it.
    def submit(self):
        """Submit the job."""
        self.submitted = True
        self.save()
        return self.job_id
