"""Test the db_manager class."""

import os
import sys

# Add the parent directory to the path to import the db_manager
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_db_manager():
    """Test the db_manager class."""
    # Need to import here to assure that the .env is set up before import
    from cosmonaut_app.db_manager import DataBaseManager

    job_id = "job123"

    data_to_insert = {
        "job_id": job_id,
        "submitted": True,
        "email": "example@example.com",
        "notified_end": False,
        "stage": 3,
        "status": "completed",
        "version": "1.0",
        "selected_road_tags": ["motorway", "primary"],
        "membership_upload": {"file_name": "test.csv"},
        "predictor_upload": {"file_name": "test_predictors.csv"},
        "epsg": 4326,
        "config": {},
    }
    DataBaseManager.add_entry(data_to_insert)
    assert DataBaseManager.check_existence(job_id)


def test_if_test_job_exists():
    """Test if the test job exists in the database."""
    from cosmonaut_app.db_manager import DataBaseManager

    assert DataBaseManager.check_existence("job123")


def test_cosmonaut_job_pydantic_save_load():
    """Test CosmonautJob with Pydantic model save and load."""
    from cosmonaut_app.cosmonaut_job import CosmonautJob

    # Create new job with defaults only
    job = CosmonautJob()
    job.save()

    # Load it back
    CosmonautJob(job_id=job.model.job_id)
