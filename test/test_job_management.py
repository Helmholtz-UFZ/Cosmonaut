"""COSMONAUT adopts the framework job management page.

The page itself (table, Delete, Clean, overlay) is the framework's and tested there.
What COSMONAUT owns is where it is mounted and where a row links to: the job link
depends on status and, for a PENDING job, on the workflow stage.
"""

import sys

import cosmo_ecosystem.pages
import dash
import pytest


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
