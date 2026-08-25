"""Database access for COSMONAUT.

The engine, the session scope, the log queries and the generic job queries come
from ``cosmo_suite.db_manager``. This module contributes the two things the
framework cannot know: the concrete ``jobs`` table, and one domain query.

**One Base, one engine.** Until slice 2 this app declared its own
``DeclarativeBase`` beside the framework's, which meant two mapper registries and
two connection pools against the same database, both mapping ``jobs`` and
``logs``. That is resolved here: ``JobTable`` is declared on the framework
``Base`` from the ``JobColumns`` mixin, and ``DbManager.job_table`` is pointed at
it. See ../docs/decisions/20260806-two-sqlalchemy-engines-transitional.md, which
this supersedes, and cosmo-suite's docs/conventions/database_schema.md.

The authoritative DDL for this table stays ``docker/init.sql``. ``JobColumns``
carries only the six columns every consumer app is measured to have; the seven
below are cosmonaut's own — extra columns are invisible to the framework's
queries, missing ones would not be, which is why the mixin is an intersection
rather than a union.
"""

import logging

from cosmo_suite.db_manager import Base, DbManager, JobColumns, SessionScope
from cosmo_suite.error_handling import JobNotFound
from sqlalchemy import JSON, Column, Integer, String

log = logging.getLogger(__name__)


class JobTable(JobColumns, Base):
    """Represents the 'jobs' table in the database.

    job_id, start_date, submitted, notified_end, status and version come from
    JobColumns. Everything below is cosmonaut's own and has no meaning to
    framework code.
    """

    __tablename__ = "jobs"

    email = Column("email", String)
    membership_upload = Column("membership_upload", JSON)
    predictor_upload = Column("predictor_upload", JSON)
    stage = Column("stage", Integer)
    epsg = Column("epsg", Integer)
    config = Column("config", JSON)
    celery_task_id = Column("celery_task_id", String, nullable=True)


# Assigned on DbManager itself, not on the subclass below: the framework pages
# call DbManager.list_jobs() directly, so `cls` there is always the base class
# and a subclass assignment would configure only this app's own call sites.
DbManager.job_table = JobTable


class DataBaseManager(DbManager):
    """Cosmonaut's database manager: framework queries plus one domain query.

    Kept under this name so the 29 existing call sites and test/conftest.py stay
    unchanged.
    """

    @classmethod
    def get_stage(cls, job_id):
        """Retrieve the stage of a specific job entry based on its job ID.

        Domain-only: `stage` tracks progress through the upload → street
        selection → routing workflow and exists in no other consumer app.

        Parameters:
        job_id (str): The unique identifier for the job.

        Returns:
        int: The stage of the job.

        Raises:
        JobNotFound: If the job with the provided job ID does not exist.
        """
        with SessionScope(cls._get_session()) as session:
            job_row = session.query(JobTable).filter_by(job_id=job_id).first()
            if job_row is None:
                raise JobNotFound(job_id)
            return job_row.stage
