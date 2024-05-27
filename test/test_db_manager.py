"""Test the db_manager class."""

import datetime

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_db_manager():
    """Test the db_manager class."""
    # Need to import here to assure that the .env is set up before import
    from cosmonaut_app.db_manager import DataBaseManager

    job_id = "job123"

    data_to_insert = {
        "job_id": job_id,
        "start_date": datetime.date(2024, 5, 27),
        "input_data": {"param1": 10, "param2": "value"},
        "files": [b"binary_data1", b"binary_data2"],
        "file_names": ["file1.txt", "file2.txt"],
        "submitted": True,
        "cluster_job_id": "cluster_789",
        "email": "example@example.com",
        "notified_end": False,
        "logs": "Some log information",
        "status": "completed",
        "version": 1.0,
    }
    DataBaseManager.add_entry(data_to_insert)
    assert DataBaseManager.check_existence(job_id)

def test_if_test_job_exists():
    """Test if the test job exists in the database."""
    from cosmonaut_app.db_manager import DataBaseManager

    assert DataBaseManager.check_existence("job123")


def test_health_check():
    """Test the health check."""
    from cosmonaut_app.db_manager import DataBaseManager

    DataBaseManager.write_health(200, "All good")
    check_time, status, message = DataBaseManager.get_health()
    assert status == 200
    assert message == "All good"
    assert isinstance(check_time, datetime.datetime)
    assert isinstance(status, int)
    assert isinstance(message, str)