"""Test the nightly cleanup task against real Postgres and object storage."""

import datetime
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
    save_files,
)

from cosmonaut_app.background_job_manager import NAME_MAINTENANCE_CLEANUP_TASK
from cosmonaut_app.celery_app import celery
from cosmonaut_app.config import DAYS_DELETE_SUBMITTED
from cosmonaut_app.db_manager import DataBaseManager
from test.help_functions_tests import job_row

FILE_NAME = "route.gpx"


def _remote_files(job_id):
    """List the objects stored below job_id's remote prefix."""
    return get_remote_files(
        f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{job_id}"
    )


def test_cleanup_removes_an_expired_job_this_pod_never_touched_from_storage():
    """An expired job whose files live only in remote storage loses them too.

    On Kubernetes the pod running the nightly cleanup usually never handled the
    job, so it has no local work dir. Remote deletion must follow the row, not
    the local disk, or the bucket grows without bound.
    """
    job_id = "test_cleanup_expired_remote_only"
    work_dir = JOB_WORK_DIR_TEMPLATE.format(job_id=job_id)
    # One day past the boundary, so the test does not hinge on how the rule
    # treats the expiry day itself.
    start_date = datetime.date.today() - datetime.timedelta(
        days=DAYS_DELETE_SUBMITTED + 1
    )
    DataBaseManager.add_entry(job_row(job_id, start_date=start_date))
    os.makedirs(work_dir, exist_ok=True)
    with open(os.path.join(work_dir, FILE_NAME), "w", encoding="UTF-8") as f_handle:
        f_handle.write("<gpx/>")
    save_files(job_id)
    shutil.rmtree(work_dir)
    assert _remote_files(job_id) == {FILE_NAME}

    try:
        # Calling the registered task runs its body in this process, through
        # the same name the beat schedule and the worker use.
        celery.tasks[NAME_MAINTENANCE_CLEANUP_TASK]()

        assert not DataBaseManager.check_existence(job_id)
        assert _remote_files(job_id) == set()
    finally:
        delete_directory_from_storage(job_id)
        shutil.rmtree(work_dir, ignore_errors=True)
        if DataBaseManager.check_existence(job_id):
            DataBaseManager.delete_job(job_id)
