"""Test that a job's log reaches the web when web and worker share no disk.

ADR 0001 (cosmo-ecosystem): the remote prefix is authoritative, the work dir is
a cache. Runs against real Postgres and object storage; outcomes only: what the
log read returns, and how many rclone processes it starts.
"""

import os
import shutil

import pytest
from cosmo_ecosystem import job_persistence
from cosmo_ecosystem.object_storage_manager import delete_directory_from_storage

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_RUNNING,
    LOG_FILE_NAME,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from test.help_functions_tests import another_pod_meanwhile

_LOG = "worker line 1\nworker line 2\n"


def _make_job(status):
    job = CosmonautJob()
    job.model.status = status
    with open(os.path.join(job.working_dir, LOG_FILE_NAME), "w") as f:
        f.write(_LOG)
    job.save()
    return job


@pytest.fixture
def make_job():
    """Yield a factory for saved jobs whose log is in object storage."""
    jobs = []

    def factory(status):
        jobs.append(_make_job(status))
        return jobs[-1]

    yield factory
    for job in jobs:
        job_id = job.model.job_id
        delete_directory_from_storage(job_id)
        shutil.rmtree(job_persistence.local_dir(job_id), ignore_errors=True)
        if DataBaseManager.check_existence(job_id):
            DataBaseManager.delete_job(job_id)


def test_a_finished_jobs_log_is_read_from_storage_on_a_pod_without_it(
    make_job, rclone_transfers
):
    job = make_job(JOB_STATUS_COMPLETED)

    with another_pod_meanwhile(job) as other:
        rclone_transfers.clear()

        assert other.get_logs() == _LOG
        pulled = len(rclone_transfers)
        assert pulled == 1

        # One pull; after that the log is local.
        assert other.get_logs() == _LOG
        assert len(rclone_transfers) == pulled


def test_a_running_jobs_log_is_read_locally_without_rclone(
    make_job, rclone_transfers
):
    job = make_job(JOB_STATUS_RUNNING)
    rclone_transfers.clear()

    assert job.get_logs() == _LOG
    with another_pod_meanwhile(job) as other:
        assert other.get_logs() == "No log file found."

    assert rclone_transfers == []
