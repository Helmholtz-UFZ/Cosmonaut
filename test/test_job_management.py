"""COSMONAUT adopts the framework job management page.

The page itself (table, Delete, Clean, overlay) is the framework's and tested there.
What COSMONAUT owns is where it is mounted and where a row links to: the job link
depends on status and, for a PENDING job, on the workflow stage.
"""

import importlib
import sys

import cosmo_ecosystem.pages
import dash
import pytest
from cosmo_ecosystem.constants.html_ids import DELETE_BUTTON_JOB_MANAGEMENT_ID
from dash._callback_context import context_value
from dash._utils import AttributeDict

from cosmonaut_app.constants.general import JOB_STATUS_RUNNING
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from test.help_functions_tests import remove_job, set_run_columns


def test_job_management_page_is_registered_under_job_management(dash_app):
    paths = {page["path"] for page in dash.page_registry.values()}

    assert dash.page_registry["pages.job_management"]["path"] == "/job-management"
    assert "/job-manager" not in paths
    # Served by the framework module, not a local copy registered under the same key.
    assert (
        dash.page_registry["pages.job_management"]["layout"]
        is sys.modules["cosmo_ecosystem.pages.job_management"].layout
    )


@pytest.mark.parametrize(
    ("status", "stage", "expected"),
    [
        ("COMPLETED", 5, "/job/abc123/route-download"),
        ("RUNNING", 4, "/job/abc123/route-computation"),
        ("FAILED", 4, "/job/abc123/route-computation"),
        ("PENDING", 0, "/job/abc123/user-info"),
        ("PENDING", 1, "/job/abc123/data-upload"),
        ("PENDING", 2, "/job/abc123/street-selection"),
        ("PENDING", 3, "/job/abc123/routing-params"),
        ("PENDING", 4, "/job/abc123/route-computation"),
        # Rows written before stage 5 was kept to COMPLETED jobs.
        ("PENDING", 5, "/job/abc123/route-computation"),
    ],
)
def test_job_link_resumes_where_the_job_stands(dash_app, status, stage, expected):
    row = {
        "status": status,
        "stage": stage,
        "start_date": None,
        "submitted": False,
    }

    assert cosmo_ecosystem.pages.job_link("abc123", row) == expected


@pytest.fixture(scope="module")
def job_management_page():
    """Return the framework's job management page as the app mounts it.

    Page modules call ``register_page`` at import, which needs a Dash app with
    pages enabled to exist first, so the app's page module is imported here
    rather than at the top of the module (a deliberate departure from the
    top-level import rule).
    """
    dash.Dash(__name__, use_pages=True, pages_folder="")
    importlib.import_module("cosmonaut_app.pages.job_management")
    return sys.modules["cosmo_ecosystem.pages.job_management"]


def test_delete_of_a_running_job_keeps_it_and_tells_the_user_to_cancel_or_wait(
    job_management_page, monkeypatch
):
    """The app's page is the framework's: its Delete reaches the row, which
    refuses a RUNNING job, and the hint names the job."""
    job = CosmonautJob()
    job_id = job.job_id
    set_run_columns(job_id, status=JOB_STATUS_RUNNING)
    page = job_management_page
    # The table rows link to pages of the running app, which this test has not
    # registered; the hint and the row are what is under test.
    monkeypatch.setattr(page, "build_rows", lambda jobs: [])
    context_value.set(
        AttributeDict(
            triggered_inputs=[
                {"prop_id": f"{DELETE_BUTTON_JOB_MANAGEMENT_ID}.n_clicks", "value": 1}
            ]
        )
    )
    try:
        _rows, _selected, hint, _overlay = page.job_management_dashboard(
            1, None, None, None, [{"job_id": f"[{job_id}](/job/{job_id})"}]
        )

        assert job_id in hint.children
        assert "cancel or wait" in hint.children
        assert DataBaseManager.check_existence(job_id)
    finally:
        remove_job(job_id)


def test_deleting_a_running_job_through_the_job_object_is_refused():
    job = CosmonautJob()
    set_run_columns(job.job_id, status=JOB_STATUS_RUNNING)
    try:
        deleted = job.delete()

        assert deleted is False
        assert DataBaseManager.check_existence(job.job_id)
    finally:
        remove_job(job.job_id)
