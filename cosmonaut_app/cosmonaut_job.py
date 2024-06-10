import logging
import os
import uuid
from datetime import date

from cosmonaut_app.config import (
    WEB_WORK_DIR,
    DAYS_DELETE_SUBMITTED,
    DAYS_DELETE_NOT_SUBMITTED,
)

from cosmonaut_app.db_manager import DataBaseManager
from minio_manager import MiniIOManager


def get_attributes(clazz):
    """Retrieve a list of non-method attributes of a class."""
    return [
        name
        for name, attr in clazz.__dict___.items()
        if not name.startswith("__")
        and not callable(attr)
        and not type(attr) is staticmethod
    ]


class CosmonautJob:
    """This class represents a job submission by the user.

    It submits jobs to the PostgreSQL database, uploads the file to the MinIO object storage and can retrieve the job again.
    """

    job_id = None
    start_date = None
    end_date = None
    status = None
    submitted = None
    file_names = None
    email = None

    def __init__(
        self,
        job_id=None,
        base_work_dir=WEB_WORK_DIR,
    ):
        """Init class by id or make a new one."""
        self.base_work_dir = base_work_dir
        if job_id is not None:
            logging.debug(f"load job with id {job_id}")
            self.load(job_id)
        else:
            logging.debug("create new job")
            self._blank_job()

    def __str__(self):
        """Return a string representation of the job."""
        return self.job_id

    def load(self):
        """get job information from database, load the data from minIO and store files in working dir."""
        logging.debug(f"load job")

        # get job information from database
        class_attributes = get_attributes(self.job_id)
        for name, value in DataBaseManager.get_job_columns(self.job_id):
            if name == "files":
                files = value
                continue
            if name not in class_attributes:
                raise AttributeError(f"CosmonautJob has no attribute named {name}")
            setattr(self, name, value)

        # copy files from minIO to working directory
        working_dir = os.path.join(self.base_work_dir, self.job_id)
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)

        for f_name in self.file_names:
            if f_name in os.listdir((working_dir)):
                logging.debug(f"file {f_name} already exists")
                continue
            # download file from minIO
            MiniIOManager.download_file(f_name, os.path.join(working_dir, f_name))
            with open(os.path.join(working_dir, f_name), "bw") as f_handle:
                f_handle.write(files[self.file_names.index(f_name)])

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

    def save(self):
        """Save the job to the database and upload files to MinIO."""
        logging.debug(f"save job {self.job_id}")
        # save job to database
        DataBaseManager.add_entry(
            {
                "job_id": self.job_id,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "status": self.status,
                "submitted": self.submitted,
                "file_names": self.file_names,
                "email": self.email,
            }
        )
        # TODO upload files to MinIO - not implemented yet
        # working_dir = self.base_work_dir #os.path.join(self.base_work_dir, self.job_id)
        # for f_name in os.listdir(working_dir):
        #     MiniIOManager.upload_file(os.path.join(self.base_work_dir, f_name), f_name)

    def delete(self):
        """Delete the job from the database and MinIO."""
        logging.debug(f"delete job {self.job_id}")
        # delete job from database
        DataBaseManager.delete_job(self.job_id)
        # delete files from MinIO
        for f_name in self.file_names:
            MiniIOManager.delete_file(f_name)

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
