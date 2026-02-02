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
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from cosmonaut_app.config import (
    POSTGRES_HOST_NAME,
    POSTGRES_NAME,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from cosmonaut_app.error_handling import JobNotFound


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

    database_url = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST_NAME}:{POSTGRES_PORT}/{POSTGRES_NAME}"
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
    def list_jobs(cls):
        """List all jobs in the database with their metadata.

        Returns
        -------
        dict
            Dictionary where keys are job_id and values are dicts with:
            - start_date (date): Job creation date
            - submitted (bool): Whether job was submitted
            - status (str): Job status
            - email (str): User email
            - celery_task_id (str|None): Celery task ID if submitted
        """
        with SessionScope(cls.Session) as session:
            job_rows = session.query(JobTable).all()

            job_info = {}
            for job_row in job_rows:
                job_info[job_row.job_id] = {
                    "start_date": job_row.start_date,
                    "submitted": job_row.submitted,
                    "status": job_row.status,
                    "email": job_row.email or "N/A",
                    "celery_task_id": job_row.celery_task_id,
                }
            return job_info

    @classmethod
    def query_logs(
        cls,
        date: str,
        sh: int,
        sm: int,
        eh: int,
        em: int,
        levels: List[str],
        pid: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query logs from the database with specified filters.

        Parameters:
        -----------
        date : str
            Date in the format 'YYYY-MM-DD'
        sh : int
            Start hour (0-23)
        sm : int
            Start minute (0-59)
        eh : int
            End hour (0-23)
        em : int
            End minute (0-59)
        levels : list
            List of log levels to include (e.g., ['INFO', 'ERROR'])
        pid : int, optional
            Process ID to filter logs by

        Returns:
        --------
        list
            List of dictionaries containing log records
        """
        logging.debug(f"Querying logs from {date} {sh}:{sm} to {date} {eh}:{em}")

        start_datetime = datetime.strptime(
            f"{date} {sh:02d}:{sm:02d}:00", "%Y-%m-%d %H:%M:%S"
        )
        end_datetime = datetime.strptime(
            f"{date} {eh:02d}:{em:02d}:59", "%Y-%m-%d %H:%M:%S"
        )

        # Create session directly (not using SessionScope)
        session = cls.Session()
        try:
            query = session.query(LogTable).filter(
                LogTable.timestamp >= start_datetime,
                LogTable.timestamp <= end_datetime,
                LogTable.level.in_(levels),
            )

            if pid is not None:
                query = query.filter(LogTable.pid == pid)

            # Order results by timestamp
            query = query.order_by(LogTable.timestamp)

            # Execute query and convert results to dictionaries
            logs = [log.to_dict() for log in query.all()]

            return logs
        finally:
            session.close()

    @classmethod
    def delete_logs_older_than(cls, cutoff_datetime):
        """Delete log entries older than the specified datetime.

        Parameters
        ----------
        cutoff_datetime : datetime
            Delete all logs with timestamp older than this

        Returns
        -------
        int
            Number of log records deleted
        """
        logging.info(f"Deleting logs older than {cutoff_datetime}")

        with SessionScope(cls.Session) as session:
            # Count logs before deletion
            count_query = session.query(LogTable).filter(
                LogTable.timestamp < cutoff_datetime
            )
            count = count_query.count()

            # Delete logs
            count_query.delete(synchronize_session=False)
            session.commit()

            logging.info(f"Deleted {count} log records older than {cutoff_datetime}")
            return count


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
    epsg = Column("epsg", Integer)
    config = Column("config", JSON)
    celery_task_id = Column("celery_task_id", String, nullable=True)
    start_date = Column(Date, nullable=False, default=date.today)


class LogTable(Base):
    """SQLAlchemy model for the logs table."""

    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=False), nullable=False)
    pid = Column(Integer, nullable=False)
    level = Column(String(10), nullable=False)
    module = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)

    def to_dict(self):
        """Convert log record to dictionary format."""
        return {
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "pid": self.pid,
            "level": self.level,
            "message": self.message,
            "module": self.module,
        }
