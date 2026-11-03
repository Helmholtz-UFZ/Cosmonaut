"""Test the db_manager class."""

from sqlalchemy import inspect

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager, JobTable
from test.help_functions_tests import job_row

TEST_JOB_DATA = job_row("job12345678")


def test_db_manager():
    """Test the db_manager class."""
    DataBaseManager.add_entry(TEST_JOB_DATA)
    assert DataBaseManager.check_existence(TEST_JOB_DATA["job_id"])


def test_if_test_job_exists():
    """Test if the test job exists in the database."""
    assert DataBaseManager.check_existence(TEST_JOB_DATA["job_id"])


def test_cosmonaut_job_pydantic_save_load():
    """Test CosmonautJob with Pydantic model save and load."""
    # Create new job with defaults only
    job = CosmonautJob()
    job.save()

    # Load it back
    CosmonautJob(job_id=job.model.job_id)


def test_the_jobs_table_from_init_sql_has_every_column_the_job_table_maps():
    """docker/init.sql is the authoritative DDL; the mapping must not outgrow it.

    The framework's ``JobColumns`` adds columns with its releases (e.g.
    ``heartbeat_at``); a column mapped but missing in the table fails every
    query on ``jobs``.
    """
    with DataBaseManager.session_scope() as session:
        table_columns = {
            column["name"] for column in inspect(session.get_bind()).get_columns("jobs")
        }

    mapped_columns = {column.name for column in JobTable.__table__.columns}
    assert mapped_columns <= table_columns
