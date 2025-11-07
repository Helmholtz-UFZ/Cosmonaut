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
    Integer,
    String,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from cosmonaut_app.config import DB_HOST_NAME, DB_NAME, DB_PORT, DB_PW, DB_USER

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)


class SessionScope:
    """Context manager for managing database sessions with retry logic."""

    def __init__(self, session_factory):
        """Initialize the session scope with a session factory."""
        self.session_factory = session_factory
        self.max_retries = 3
        self.retry_delay = 1
        self.session = None

    def __enter__(self):
        """Create a new session and handle retries for database operations."""
        for attempt in range(self.max_retries + 1):
            try:
                self.session = self.session_factory()
                return self.session  # success
            except OperationalError as e:
                if attempt < self.max_retries:
                    logging.warning(
                        f"Database OperationalError: {e}", extra={"tag": "database"}
                    )
                    logging.warning(
                        f"Retrying operation (attempt {attempt + 1}/{self.max_retries + 1})",  # noqa
                        extra={"tag": "database"},
                    )
                    time.sleep(self.retry_delay)
                else:
                    logging.error(
                        f"Max retries ({self.max_retries}) exceeded",
                        extra={"tag": "database"},
                    )
                    raise
            except SQLAlchemyError as e:
                logging.error(f"Database error: {e}", extra={"tag": "database"})
                raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Commit or rollback the session based on exception type."""
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()

        # False means exceptions are re-raised outside the `with`
        return False


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
        f"postgresql+psycopg2://{DB_USER}:{DB_PW}@{DB_HOST_NAME}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
    )
    Session = sessionmaker(bind=engine)

    @classmethod
    def check_existence(self, job_id):
        """Check if a job with the given job ID exists in the database.

        This method queries the 'jobs' table in the database to determine
        whether a job with the provided job ID exists.

        Parameters:
        job_id (str): The unique identifier for the job.

        Returns:
        bool: True if a job with the given job ID exists, False otherwise.
        """
        logging.debug(f"Check existence of job with ID: {job_id}")
        with SessionScope(self.Session) as session:
            job_row = session.query(JobTable).filter_by(job_id=job_id).first()
            return job_row is not None

    @classmethod
    def add_entry(self, data_to_insert):
        """Add or update a job entry in the database.

        This method takes a dictionary containing job information and

        Parameters:
        data_to_insert (dict): A dictionary containing job information with keys
        equivalent to the cloumns ins JobTable.
        """
        with SessionScope(self.Session) as session:
            job_row = JobTable(**data_to_insert)
            session.merge(job_row)
            session.commit()

    @classmethod
    def update_column(self, job_id, column_dic):
        """Update a specific column in the 'JobTable' for a given job ID.

        Raises:
        JobNotFound: If the job with the provided job ID does not exist.
        """
        with SessionScope(self.Session) as session:
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
        with SessionScope(self.Session) as session:
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
        with SessionScope(self.Session) as session:
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
        with SessionScope(self.Session) as session:
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
        with SessionScope(self.Session) as session:
            job_rows = session.query(JobTable).all()

            job_info = {}
            for job_row in job_rows:
                job_info[job_row.job_id] = (job_row.start_date, job_row.submitted)
            return job_info


class JobTable(Base):
    """Represents the 'jobs' table in the database."""

    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    email = Column("email", String)
    classification_upload = Column("classification_upload", JSON)
    selected_road_tags = Column("selected_road_tags", ARRAY(String))
    submitted = Column("submitted", Boolean)
    notified_end = Column("notified_end", Boolean)
    stage = Column("stage", Integer)
    status = Column("status", String)
    version = Column("version", String)
    config = Column("config", JSON)
