"""Test the db_manager class."""

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
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
