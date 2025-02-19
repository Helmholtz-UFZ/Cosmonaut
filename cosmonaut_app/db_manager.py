"""Module for interaction between webservice and data base.

This module defines the DataBaseManager class for interacting with job entries
in a database. The DataBaseManager class provides methods to check for the
existence of a job, add or update job entries, and retrieve all columns of a
specific job entry.

Classes:
- DataBaseManager: A class for managing job entries in the database.
- JobTable: Represents the 'jobs' table in the database.
"""

import logging
import time

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    Date,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import OperationalError

from cosmonaut_app.config import DB_HOST_NAME, DB_NAME, DB_PORT, DB_PW, DB_USER

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for declarative base."""

    pass


class JobNotFound(Exception):
    """Custom exception for when a job is not found."""

    def __init__(self, job_id):
        """Add job id as attribute and format error message."""
        self.job_id = job_id
        super().__init__(f"Job with ID '{job_id}' not found")


class DataBaseManager:
    """Class for interacting with the 'jobs' table in the database.

    This class encapsulates methods to manage job entries in the 'jobs' table
    of the database. It provides functionalities to check for the existence of
    a job by its ID and to add or update job entries.

    Attributes:
    database_url (str): The URL for connecting to the PostgreSQL database.
    engine (sqlalchemy.engine.base.Engine): The database connection engine.
    Session (sqlalchemy.orm.session.sessionmaker): A session factory for
    creating sessions to interact with the database.

    Methods:
    check_existence(job_id): Check if a job with the given job ID exists in the
    database.
    add_entry(data_to_insert): Add or update a job entry in the database.
    get_job_columns(job_id): Retrieve all columns of a specific job entry based
    on its job ID.
    """

    database_url = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PW}@"
        f"{DB_HOST_NAME}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)

    @classmethod
    def check_existence(self, job_id, retries=3, delay=5):
        """Check if a job with the given job ID exists in the database.

        This method queries the 'jobs' table in the database to determine
        whether a job with the provided job ID exists.

        Parameters:
        job_id (str): The unique identifier for the job.

        Returns:
        bool: True if a job with the given job ID exists, False otherwise.
        """
        logging.debug(f"Check existence of job with ID: {job_id}")
        for attempt in range(retries):
            try:
                with self.Session() as session:
                    job_row = session.query(JobTable).filter_by(job_id=job_id).first()
                return job_row is not None
            except OperationalError as e:
                logging.error(f"Database connection failed: {e}")
                if attempt < retries - 1:
                    logging.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    raise

    @classmethod
    def add_entry(self, data_to_insert):
        """Add or update a job entry in the database.

        This method takes a dictionary containing job information and

        Parameters:
        data_to_insert (dict): A dictionary containing job information with keys
        equivalent to the cloumns ins JobTable.
        """
        with self.Session() as session:
            job_row = JobTable(**data_to_insert)
            session.merge(job_row)
            session.commit()

    @classmethod
    def update_column(self, job_id, column_dic):
        """Update a specific column in the 'JobTable' for a given job ID.

        Raises:
        JobNotFound: If the job with the provided job ID does not exist.
        """
        with self.Session() as session:
            job = session.query(JobTable).filter_by(job_id=job_id).first()
            if job is None:
                raise JobNotFound(job_id)
            for column_name, column_value in column_dic.items():
                setattr(job, column_name, column_value)
            session.commit()

    @classmethod
    def get_job_columns(self, job_id):
        """Retrieve all columns of a specific job entry based on its job ID.

        This method queries the 'jobs' table in the database to retrieve all
        columns of the job entry associated with the provided job ID.

        Parameters:
        job_id (str): The unique identifier for the job.

        Returns:
        dict: A dictionary containing all columns and their values for the
        specified job.

        Raises:
        JobNotFound: If the job with the provided job ID does not exist.
        """
        with self.Session() as session:
            job_row = session.query(JobTable).filter_by(job_id=job_id).first()
            if job_row:
                job_columns = {
                    column.name: getattr(job_row, column.name)
                    for column in JobTable.__table__.columns
                }
                return job_columns
            else:
                raise JobNotFound(job_id)

    @classmethod
    def get_stage(self, job_id):
        """Retrieve the stage of a specific job entry based on its job ID.

        This method queries the 'jobs' table in the database to retrieve the
        stage of the job entry associated with the provided job ID.

        Parameters:
        job_id (str): The unique identifier for the job.

        Returns:
        int: The stage of the job.

        Raises:
        JobNotFound: If the job with the provided job ID does not exist.
        """
        with self.Session() as session:
            job_row = session.query(JobTable).filter_by(job_id=job_id).first()
            if job_row:
                return job_row.stage
            else:
                raise JobNotFound(job_id)

    @classmethod
    def delete_job(self, job_id):
        """Delete a job entry from the database based on its job ID.

        This method deletes a job entry from the 'jobs' table in the database
        based on the provided job ID.

        Parameters:
        job_id (str): The unique identifier for the job to be deleted.

        Raises:
        JobNotFound: If the job with the provided job ID does not exist.
        """
        with self.Session() as session:
            job = session.query(JobTable).filter_by(job_id=job_id).first()
            if job:
                session.delete(job)
                session.commit()
            else:
                raise JobNotFound(job_id)

    @classmethod
    def list_jobs(self):
        """List all jobs in the database with their submission date and status.

        This method retrieves all job entries from the 'jobs' table in the
        database and returns a dictionary where the keys are 'job_id', and the
        values are a tuple containing 'start_date' and 'submitted' status
        for each job.

        Returns:
        dict: A dictionary where keys are 'job_id' and values are tuples
        containing 'start_date' and 'submitted' status.

        Example:
        {
        'job1': ('2023-09-01', True),
        'job2': ('2023-09-02', False),
        # ...
        }

        """
        with self.Session() as session:
            job_rows = session.query(JobTable).all()

            job_info = {}
            for job_row in job_rows:
                job_info[job_row.job_id] = (job_row.start_date, job_row.submitted)
            return job_info

    @classmethod
    def get_lock(self, task_type):
        """Get a lock for a specific backgroung task type.

        This method queries the TaskLockTable in the database to retrieve
        the lock for a specific background task type. If the lock does not exist,
        it will be created. The lock is used to prevent multiple instances of the
        same background task type from running concurrently. The lock is released
        with the method 'release_lock'.
        """
        logging.debug(f"Get lock for task type: {task_type}")
        with self.Session() as session:
            task_lock = (
                session.query(TaskLockTable)
                .filter_by(task_type=task_type)
                .with_for_update()
                .first()
            )
            if task_lock is None:
                task_lock = TaskLockTable(task_type=task_type, is_locked=True)
                session.add(task_lock)
            elif task_lock.is_locked:
                return False
            else:
                task_lock.is_locked = True
            session.commit()
        return True

    @classmethod
    def release_lock(self, task_type):
        """Release the lock for a specific background task type.

        This method releases the lock for a specific background task type in the
        TaskLockTable in the database. The lock is used to prevent multiple instances
        of the same background task type from running concurrently.
        """
        logging.debug(f"Release lock for task type: {task_type}")
        with self.Session() as session:
            task_lock = (
                session.query(TaskLockTable).filter_by(task_type=task_type).first()
            )
            if task_lock:
                task_lock.is_locked = False
                session.commit()


class TaskLockTable(Base):
    """Represents the 'task_lock' table in the database."""

    __tablename__ = "task_lock"

    task_type = Column(String, primary_key=True)
    is_locked = Column("is_locked", Boolean)


class JobTable(Base):
    """Represents the 'jobs' table in the database."""

    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    data_uploaded = Column("data_uploaded", Boolean)
    submitted = Column("submitted", Boolean)
    email = Column("email", String)
    notified_end = Column("notified_end", Boolean)
    stage = Column("stage", Integer)
    status = Column("status", String)
    version = Column("version", Float)
    file_names = Column("file_names", ARRAY(String))
    selected_road_tags = Column("selected_road_tags", ARRAY(String))


if __name__ == "__main__":
    DataBaseManager.check_existence("test")
