"""Start and monitor the routing computation process.

This page gives you full control over the routing calculation for your job.
Unlike the other workflow steps, the actual route computation happens here as a
background task, allowing you to monitor its progress and manage the process.

**Starting the Computation:**

Click the green "Start Computation" button to begin calculating your optimized route.
The computation runs as a background task using Celery workers, so it continues even
if you close your browser or navigate away. You can return to this page at any time
to check the status.

**Job Status:**

The status badge shows the current state of your computation:
- **PENDING** (Gray): Job created but not yet started
- **RUNNING** (Blue): Computation is actively running
- **COMPLETED** (Green): Route successfully calculated, ready to download
- **FAILED** (Red): Computation encountered an error

**Managing the Computation:**

Depending on the current status, you'll see different control buttons:
- **Start Computation**: Begins the route calculation (shown when PENDING or FAILED)
- **Cancel Computation**: Stops the running task immediately (shown when RUNNING)
- **Restart Computation**: Clears previous results and starts fresh (shown when COMPLETED or FAILED)

**Worker Information:**

The Celery Worker Information panel shows real-time details about the computation infrastructure:
- **Worker Availability**: Number of background workers available to process your job
- **Task Celery Status**: Internal task state from the Celery task queue
- **Worker Name**: Hostname of the specific worker processing your job

This information helps diagnose issues if your job stays in PENDING state (no workers available)
or if you need to report problems to system administrators.

**Computation Logs:**

Once your computation completes (COMPLETED or FAILED status), the full worker logs
automatically appear at the bottom of the page. These logs contain detailed information
about the routing calculation process, including:
- Algorithm execution steps and progress
- Parameters used for the optimization
- Statistics about the generated route
- Any warnings or errors encountered

The logs are synced from the worker container after the job finishes, so they won't
appear while the computation is still running.

**Next Step:**

When the computation completes successfully (COMPLETED status), the "Next" button
becomes enabled. Click it to proceed to the Route & Download page where you can
view the calculated route on the map and download the GPX navigation file.

NOTE: Page runs in split layout with map on left (shows data upload locations) and controls on right.
NOTE: Uses Bootstrap-only styling (no custom CSS except whiteSpace for log wrapping).
NOTE: Polling interval (3s) only active when job is RUNNING, automatically disabled when complete.
NOTE: All control callbacks include status checks to prevent duplicate operations from multiple browser tabs.
NOTE: Worker runs in separate Docker container, so real-time log streaming is not possible.
"""

import logging
from dash import html, register_page, callback, Input, Output, State, dcc
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.background_job_manager import get_background_job_manager
from cosmonaut_app.constants import (
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    START_BUTTON_ROUTE_COMPUTATION_ID,
    CANCEL_BUTTON_ROUTE_COMPUTATION_ID,
    RESTART_BUTTON_ROUTE_COMPUTATION_ID,
    STATUS_BADGE_ROUTE_COMPUTATION_ID,
    CELERY_INFO_CARD_ROUTE_COMPUTATION_ID,
    WORKER_STATUS_TEXT_ROUTE_COMPUTATION_ID,
    TASK_STATUS_TEXT_ROUTE_COMPUTATION_ID,
    WORKER_NAME_TEXT_ROUTE_COMPUTATION_ID,
    LOG_VIEWER_ROUTE_COMPUTATION_ID,
    STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID,
)
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    progress_footer,
    build_url_step,
    create_map,
    create_reset_banner,
    create_reset_modal,
)

register_page(
    __name__,
    path_template="/job/<job_id>/route-computation",
    name="Route Computation",
    title="Routing Computation",
    description="Monitor and control routing computation.",
    dynamic=True,
)


def layout(job_id):
    """Create layout for routing computation page."""
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()

    # Status badge
    status_badge = create_status_badge(status)

    # Control buttons
    control_buttons = create_control_buttons(status)

    # Celery info card
    celery_info_card = create_celery_info_card()

    # Polling interval (updates every 3 seconds when enabled)
    interval = dcc.Interval(
        id=STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID,
        interval=3000,  # milliseconds
        disabled=(status not in [JOB_STATUS_RUNNING, JOB_STATUS_PENDING]),
    )

    log_content = job.get_logs()
    log_viewer = dbc.Card(
        dbc.CardBody(
            html.Pre(
                log_content,
                id=LOG_VIEWER_ROUTE_COMPUTATION_ID,
                className="mb-0",
                style={"whiteSpace": "pre-wrap"},
            ),
            className="p-3",
        ),
        className="mb-3",
    )

    card_body = []

    # Add reset banner if not PENDING
    if status != JOB_STATUS_PENDING:
        card_body.append(create_reset_banner(job_id, status))

    # Add existing content
    card_body.extend(
        [
            html.P(
                "Monitor the routing computation status and manage the computation job.",
                className="mb-3",
            ),
            status_badge,
            control_buttons,
            html.Hr(),
            html.H5("Celery Worker Information", className="mt-3"),
            celery_info_card,
            html.Hr(),
            html.H5("Computation Logs", className="mt-3"),
            log_viewer,
            interval,
            dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id),
        ]
    )

    # Add reset modal
    card_body.append(create_reset_modal())

    routing_params_path = build_url_step("routing_params", job_id)
    route_download_path = build_url_step("route_download", job_id)

    footer = progress_footer(
        prev_url=routing_params_path,
        next_url=route_download_path,
        next_disabled=(status != JOB_STATUS_COMPLETED),
    )

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step="route_computation",
        job_id=job_id,
    )

    map = create_map(job=job)
    return page_container_split_layout(map, input_container)


def create_status_badge(status):
    """Create a status badge with appropriate color."""
    color_map = {
        JOB_STATUS_PENDING: "secondary",
        JOB_STATUS_RUNNING: "primary",
        JOB_STATUS_COMPLETED: "success",
        JOB_STATUS_FAILED: "danger",
    }

    spinner = (
        dbc.Spinner(size="sm", className="ms-2")
        if status == JOB_STATUS_RUNNING
        else None
    )

    return dbc.Row(
        [
            dbc.Col(html.Strong("Job Status:"), width="auto"),
            dbc.Col(
                dbc.Badge(
                    status,
                    id=STATUS_BADGE_ROUTE_COMPUTATION_ID,
                    color=color_map.get(status, "secondary"),
                ),
                width="auto",
            ),
            dbc.Col(spinner, width="auto") if spinner else None,
        ],
        className="mb-3 align-items-center",
    )


def create_control_buttons(status):
    """Create control buttons based on current status."""
    buttons = []

    # Start button (PENDING or FAILED)
    if status in [JOB_STATUS_PENDING, JOB_STATUS_FAILED]:
        buttons.append(
            dbc.Button(
                "Start Computation",
                id=START_BUTTON_ROUTE_COMPUTATION_ID,
                color="success",
                className="me-2",
            )
        )

    # Cancel button (RUNNING)
    if status == JOB_STATUS_RUNNING:
        buttons.append(
            dbc.Button(
                "Cancel Computation",
                id=CANCEL_BUTTON_ROUTE_COMPUTATION_ID,
                color="danger",
                className="me-2",
            )
        )

    # Restart button (COMPLETED or FAILED)
    if status in [JOB_STATUS_COMPLETED, JOB_STATUS_FAILED]:
        buttons.append(
            dbc.Button(
                "Restart Computation",
                id=RESTART_BUTTON_ROUTE_COMPUTATION_ID,
                color="warning",
                className="me-2",
            )
        )

    return html.Div(buttons, className="mb-3") if buttons else html.Div()


def create_celery_info_card():
    """Create card for displaying Celery worker information."""
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    dbc.ListGroup(
                        [
                            dbc.ListGroupItem(
                                [
                                    html.Strong("Worker Availability: "),
                                    html.Span(
                                        "Checking...",
                                        id=WORKER_STATUS_TEXT_ROUTE_COMPUTATION_ID,
                                    ),
                                ]
                            ),
                            dbc.ListGroupItem(
                                [
                                    html.Strong("Task Celery Status: "),
                                    html.Span(
                                        "N/A",
                                        id=TASK_STATUS_TEXT_ROUTE_COMPUTATION_ID,
                                    ),
                                ]
                            ),
                            dbc.ListGroupItem(
                                [
                                    html.Strong("Worker Name: "),
                                    html.Span(
                                        "N/A",
                                        id=WORKER_NAME_TEXT_ROUTE_COMPUTATION_ID,
                                    ),
                                ]
                            ),
                        ],
                        flush=True,
                    )
                ]
            )
        ],
        id=CELERY_INFO_CARD_ROUTE_COMPUTATION_ID,
        className="mb-3",
    )


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(STATUS_BADGE_ROUTE_COMPUTATION_ID, "children"),
    Output(STATUS_BADGE_ROUTE_COMPUTATION_ID, "color"),
    Output(STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID, "disabled"),
    Output(WORKER_STATUS_TEXT_ROUTE_COMPUTATION_ID, "children"),
    Output(TASK_STATUS_TEXT_ROUTE_COMPUTATION_ID, "children"),
    Output(WORKER_NAME_TEXT_ROUTE_COMPUTATION_ID, "children"),
    Output(LOG_VIEWER_ROUTE_COMPUTATION_ID, "children"),
    Input(STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID, "n_intervals"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=False,
)
def update_status_and_celery_info(n_intervals, job_id):
    """Poll job status and Celery worker information."""
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()

    # Status badge color
    color_map = {
        JOB_STATUS_PENDING: "secondary",
        JOB_STATUS_RUNNING: "primary",
        JOB_STATUS_COMPLETED: "success",
        JOB_STATUS_FAILED: "danger",
    }

    # Disable interval if not running
    disable_interval = status != JOB_STATUS_RUNNING

    # Get Celery worker information
    job_manager = get_background_job_manager()
    tasks_overview = job_manager.get_all_tasks_overview()

    # Check worker availability (correct key is "workers" not "active_workers")
    workers = tasks_overview.get("workers", [])
    worker_available = len(workers) > 0
    worker_status_text = (
        f"{len(workers)} worker(s) available"
        if worker_available
        else "No workers available"
    )

    # Get task status and worker name
    task_status_text = "N/A"
    worker_name_text = "N/A"

    if job.model.celery_task_id:
        celery_status_info = job_manager.get_job_status(job.model.celery_task_id)
        task_status_text = celery_status_info.get("status", "UNKNOWN")

        # Find which worker is processing this task by searching active tasks
        active_tasks = tasks_overview.get("active", [])
        for task in active_tasks:
            if task.get("id") == job.model.celery_task_id:
                worker_name_text = task.get("worker", "Unknown")
                break

        # If not in active, check reserved tasks
        if worker_name_text == "N/A":
            reserved_tasks = tasks_overview.get("reserved", [])
            for task in reserved_tasks:
                if task.get("id") == job.model.celery_task_id:
                    worker_name_text = task.get("worker", "Unknown")
                    break

    log_content = job.get_logs()

    return (
        status,
        color_map.get(status, "secondary"),
        disable_interval,
        worker_status_text,
        task_status_text,
        worker_name_text,
        log_content,
    )


@callback(
    Output(JOB_ID_STORE_SHARED_ID, "data", allow_duplicate=True),
    Input(START_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def start_computation(n_clicks, job_id):
    """Start the routing computation.

    Checks current status to prevent duplicate submissions (multiple tabs).
    """
    if n_clicks is None:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    current_status = job.get_status()

    # Prevent duplicate submission if already running
    if current_status == JOB_STATUS_RUNNING:
        logging.warning(f"Job {job_id} already running, ignoring start request")
        raise PreventUpdate

    # Only start if PENDING or FAILED
    if current_status in [JOB_STATUS_PENDING, JOB_STATUS_FAILED]:
        job.submit()
        logging.info(f"Started computation for job {job_id}")
    else:
        logging.warning(f"Cannot start job {job_id} with status {current_status}")
        raise PreventUpdate

    return job_id  # Trigger refresh


@callback(
    Output(JOB_ID_STORE_SHARED_ID, "data", allow_duplicate=True),
    Input(CANCEL_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def cancel_computation(n_clicks, job_id):
    """Cancel the running computation.

    Checks current status to prevent duplicate cancellations (multiple tabs).
    """
    if n_clicks is None:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    current_status = job.get_status()

    # Only cancel if actually running
    if current_status != JOB_STATUS_RUNNING:
        logging.warning(
            f"Job {job_id} not running (status: {current_status}), ignoring cancel request"
        )
        raise PreventUpdate

    if job.model.celery_task_id:
        job_manager = get_background_job_manager()
        job_manager.revoke_job(job.model.celery_task_id, terminate=True)
        logging.info(f"Cancelled computation for job {job_id}")
    else:
        logging.warning(f"Job {job_id} has no celery_task_id to cancel")
        raise PreventUpdate

    return job_id  # Trigger refresh


@callback(
    Output(JOB_ID_STORE_SHARED_ID, "data", allow_duplicate=True),
    Input(RESTART_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def restart_computation(n_clicks, job_id):
    """Restart the computation (cancel if running, then start).

    Checks current status to handle edge cases (multiple tabs).
    """
    if n_clicks is None:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    current_status = job.get_status()

    # If currently running, don't restart (user should cancel first)
    if current_status == JOB_STATUS_RUNNING:
        logging.warning(f"Job {job_id} is running, cannot restart. Cancel first.")
        raise PreventUpdate

    # Cancel existing task if it exists (safety check)
    if job.model.celery_task_id:
        job_manager = get_background_job_manager()
        job_manager.revoke_job(job.model.celery_task_id, terminate=True)

    # Reset status and submit new task
    job.model.status = JOB_STATUS_PENDING
    job.save()
    job.submit()

    logging.info(f"Restarted computation for job {job_id}")

    return job_id  # Trigger refresh
