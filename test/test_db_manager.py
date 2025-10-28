"""Test the db_manager class."""

import datetime
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
        "start_date": datetime.date(2024, 5, 27),
        "end_date": datetime.date(2024, 5, 28),
        "data_uploaded": True,
        "submitted": True,
        "email": "example@example.com",
        "notified_end": False,
        "stage": 3,
        "status": "completed",
        "version": 1.0,
        "selected_road_tags": ["motorway", "primary"],
    }
    DataBaseManager.add_entry(data_to_insert)
    assert DataBaseManager.check_existence(job_id)


def test_if_test_job_exists():
    """Test if the test job exists in the database."""
    from cosmonaut_app.db_manager import DataBaseManager

    assert DataBaseManager.check_existence("job123")
