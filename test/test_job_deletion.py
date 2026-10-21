"""Test deleting a CosmonautJob against real Postgres and object storage."""

import os
import shutil

from cosmo_ecosystem.config import (
    JOB_WORK_DIR_TEMPLATE,
    OBJECT_STORAGE_BUCKET,
    OBJECT_STORAGE_REMOTE_NAME,
)
from cosmo_ecosystem.object_storage_manager import (
    delete_directory_from_storage,
    get_remote_files,
)

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager


def _remote_files(job_id):
    """List the objects stored below job_id's remote prefix."""
    return get_remote_files(
        f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{job_id}"
    )


def _cleanup(job_id):
    """Remove whatever a failed test left behind for job_id."""
    work_dir = JOB_WORK_DIR_TEMPLATE.format(job_id=job_id)
    delete_directory_from_storage(job_id)
    shutil.rmtree(work_dir, ignore_errors=True)
    if DataBaseManager.check_existence(job_id):
        DataBaseManager.delete_job(job_id)


def test_deleting_a_job_removes_its_local_work_dir_too():
    """Job.delete removes row, remote prefix and, new, the local work dir."""
    job = CosmonautJob()
    job_id = job.model.job_id
    assert os.path.isdir(job.working_dir)
    assert _remote_files(job_id) != set()

    try:
        job.delete()

        assert not os.path.exists(job.working_dir)
        assert not DataBaseManager.check_existence(job_id)
        assert _remote_files(job_id) == set()
    finally:
        _cleanup(job_id)
