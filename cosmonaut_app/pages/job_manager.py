"""Manage all jobs from a central dashboard.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This administrative page provides a comprehensive overview of all jobs in the system.
You can:
- View all jobs in a table with status, start date, and submission details
- See job status at a glance with color coding (PENDING=orange, RUNNING=green,
  COMPLETED=blue, FAILED=red)
- Select and delete individual jobs or multiple jobs at once
- Trigger cleanup operations to remove old jobs automatically
- Access individual job pages directly from the table by clicking Job ID

The table uses color coding to quickly identify job statuses. You can select rows to
perform bulk operations like deletion. Use the cleanup function to automatically remove
jobs that exceed retention periods (2 days for unsubmitted, 60 days for submitted jobs).

# Notes (This section is for developer notes and will not appear in the user documentation.)

This docstring is displayed on the documentation webpage.
"""

import logging
import re

import dash
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash import Input, Output, State, callback, html

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
)
from cosmonaut_app.constants.html_ids import (
    CLEAN_UP_BUTTON_JOB_MANAGER_ID,
    DELETE_BUTTON_JOB_MANAGER_ID,
    JOBS_TABLE_JOB_MANAGER_ID,
    LOADING_OVERLAY_SHARED_ID,
    REFRESH_BUTTON_JOB_MANAGER_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.layout import create_header, page_container_column_layout, build_url_step
from cosmonaut_app.tasks.maintenance_tasks import clean_up_jobs

log = logging.getLogger(__name__)

dash.register_page(
    __name__,
    path="/job-manager",
    name="Job Manager",
    title="COSMONAUT - Job Manager",
    description="Centralized management interface for all COSMONAUT jobs.",
)


# ============================================================================
# Helper Functions
# ============================================================================


_STAGE_TO_PAGE = {
    0: "user_info",
    1: "data_upload",
    2: "street_selection",
    3: "routing_params",
    4: "route_computation",
}


def _resolve_reload_url(job_id: str, status: str, stage: int) -> str:
    """Resolve the appropriate page URL when reloading a job from the job manager.

    Maps status and stage to the page where the user should resume their work.
    Status takes priority: COMPLETED always goes to route_download, RUNNING/FAILED to
    route_computation. For PENDING jobs, stage determines the page.

    Args:
        job_id: The job ID
        status: Job status (PENDING/RUNNING/COMPLETED/FAILED)
        stage: Workflow stage (0-4), only used if status is PENDING

    Returns:
        URL path to navigate to
    """
    if status == JOB_STATUS_COMPLETED:
        return build_url_step("route_download", job_id)
    if status in (JOB_STATUS_RUNNING, JOB_STATUS_FAILED):
        return build_url_step("route_computation", job_id)
    # PENDING: use stage to determine page
    page = _STAGE_TO_PAGE.get(stage, "user_info")
    return build_url_step(page, job_id)


def format_jobs_for_table(jobs_dict):
    """Format jobs dictionary for AgGrid display.

    Parameters
    ----------
    jobs_dict : dict
        Dictionary from DataBaseManager.list_jobs()
        Format: {job_id: {status, start_date, submitted, email, celery_task_id, stage}}

    Returns
    -------
    list
        List of dicts formatted for AgGrid with columns:
        - job_id (markdown link to smart reload page)
        - status (color-coded)
        - start_date (YYYY-MM-DD)
        - submitted (Yes/No)
    """
    rows = []

    for job_id, job_data in jobs_dict.items():
        # Create markdown link for job_id, navigating to the appropriate page based on status/stage
        job_link = _resolve_reload_url(job_id, job_data["status"], job_data["stage"])
        job_id_markdown = f"[{job_id}]({job_link})"

        # Format submitted as Yes/No
        submitted_display = "Yes" if job_data["submitted"] else "No"

        # Format start_date
        start_date_str = job_data["start_date"].strftime("%Y-%m-%d")

        rows.append(
            {
                "job_id": job_id_markdown,
                "status": job_data["status"],
                "start_date": start_date_str,
                "submitted": submitted_display,
            }
        )

    return rows


# ============================================================================
# Layout Components
# ============================================================================


table = dag.AgGrid(
    id=JOBS_TABLE_JOB_MANAGER_ID,
    columnDefs=[
        {
            "field": "job_id",
            "headerName": "Job ID",
            "cellRenderer": "markdown",
            "cellStyle": {"textAlign": "left", "fontFamily": "monospace"},
        },
        {
            "field": "status",
            "headerName": "Status",
            "cellStyle": {
                "styleConditions": [
                    {
                        "condition": f"params.value === '{JOB_STATUS_COMPLETED}'",
                        "style": {"backgroundColor": "#3498db"},
                    },
                    {
                        "condition": f"params.value === '{JOB_STATUS_RUNNING}'",
                        "style": {"backgroundColor": "#2ecc71"},
                    },
                    {
                        "condition": f"params.value === '{JOB_STATUS_FAILED}'",
                        "style": {"backgroundColor": "#e74c3c"},
                    },
                    {
                        "condition": f"params.value === '{JOB_STATUS_PENDING}'",
                        "style": {"backgroundColor": "#f39c12"},
                    },
                ],
            },
        },
        {"field": "start_date", "headerName": "Start Date"},
        {"field": "submitted", "headerName": "Submitted"},
    ],
    rowData=[],
    defaultColDef={"cellStyle": {"textAlign": "center"}},
    dashGridOptions={
        "rowSelection": {"mode": "multiRow"},
        "suppressCellFocus": True,
        "overlayNoRowsTemplate": "<div class='text-muted py-3'>No jobs found.</div>",
    },
    columnSize="responsiveSizeToFit",
)


def layout():
    """Create the job manager page layout.

    Returns
    -------
    dash component
        Complete page layout with header, controls, and table
    """
    log.info("Generating job manager page layout")
    header = create_header(
        "Job Manager",
        "Centralized management of all COSMONAUT jobs",
        bg_color="bg-info",
        rounded=False,
    )

    # Button controls - buttons on the right side like cosmopolitan
    button_group = [
        dbc.Button(
            [
                html.I(className="bi bi-arrow-clockwise me-1"),
                "Refresh Jobs",
            ],
            id=REFRESH_BUTTON_JOB_MANAGER_ID,
            color="primary",
            className="ms-2 float-end",
        ),
        dbc.Button(
            [
                html.I(className="bi bi-trash me-1"),
                "Delete Selection",
            ],
            id=DELETE_BUTTON_JOB_MANAGER_ID,
            color="danger",
            className="ms-2 float-end",
        ),
        dbc.Button(
            [
                html.I(className="bi bi-recycle me-1"),
                "Clean",
            ],
            id=CLEAN_UP_BUTTON_JOB_MANAGER_ID,
            color="warning",
            className="ms-2 float-end",
        ),
    ]

    button_row = dbc.Row(
        dbc.Col(
            button_group,
        ),
        className="m-2",
    )

    # Jobs table
    table_row = dbc.Row(
        dbc.Col(
            table,
        ),
        className="m-2",
    )

    # Assemble page - using same structure as cosmopolitan
    return page_container_column_layout(
        [
            header,
            button_row,
            table_row,
        ]
    )


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(JOBS_TABLE_JOB_MANAGER_ID, "rowData"),
    Output(JOBS_TABLE_JOB_MANAGER_ID, "selectedRows"),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(REFRESH_BUTTON_JOB_MANAGER_ID, "n_clicks"),
    Input(DELETE_BUTTON_JOB_MANAGER_ID, "n_clicks"),
    Input(CLEAN_UP_BUTTON_JOB_MANAGER_ID, "n_clicks"),
    State(JOBS_TABLE_JOB_MANAGER_ID, "selectedRows"),
    prevent_initial_call=True,
)
def manage_jobs(refresh_clicks, delete_clicks, clean_clicks, selected_rows):
    """Handle job management operations.

    This callback handles:
    - Refresh: Reload job data from database
    - Delete: Remove selected jobs
    - Clean: Run cleanup task to remove old jobs

    Parameters
    ----------
    refresh_clicks : int
        Number of times refresh button was clicked
    delete_clicks : int
        Number of times delete button was clicked
    clean_clicks : int
        Number of times clean up button was clicked
    selected_rows : list
        List of selected row dicts from AgGrid

    Returns
    -------
    tuple
        (row_data, selected_rows, loading_overlay_state)
    """
    log.info("Job management callback triggered")

    # Determine which button was clicked
    triggered_ids = {
        t["prop_id"].split(".")[0]
        for t in dash.callback_context.triggered
        if t["value"] is not None
    }

    # Handle DELETE operation
    if DELETE_BUTTON_JOB_MANAGER_ID in triggered_ids and selected_rows:
        log.info(f"Deleting {len(selected_rows)} selected jobs")

        for row in selected_rows:
            # Extract job_id from markdown link format: [job_id](url)
            job_id = re.findall(r"\[(.*?)\]", row["job_id"])[0]
            log.info(f"Deleting job: {job_id}")

            try:
                job = CosmonautJob(job_id=job_id, sync_files=False)
                job.delete()
                log.info(f"Successfully deleted job: {job_id}")
            except Exception as e:
                log.error(f"Failed to delete job {job_id}: {e}")

    # Handle CLEANUP operation
    elif CLEAN_UP_BUTTON_JOB_MANAGER_ID in triggered_ids:
        log.info("Running cleanup task to remove old jobs")

        try:
            # Call cleanup directly (blocking, but typically fast)
            clean_up_jobs()
            log.info("Cleanup task completed successfully")
        except Exception as e:
            log.error(f"Cleanup task failed: {e}")

    # Fetch fresh job data from database
    jobs_dict = DataBaseManager.list_jobs()
    log.debug(f"Retrieved {len(jobs_dict)} jobs from database")

    # Format for table display
    table_rows = format_jobs_for_table(jobs_dict)

    log.info(f"Job manager refreshed - {len(table_rows)} jobs displayed")

    # Reset selection after delete/clean, hide loading overlay
    if triggered_ids & {DELETE_BUTTON_JOB_MANAGER_ID, CLEAN_UP_BUTTON_JOB_MANAGER_ID}:
        return table_rows, [], False

    # For refresh, keep current selection
    return table_rows, dash.no_update, False
