"""Start and monitor the routing computation process.

# User documentation (This section is for user documentation and will appear in the user documentation.)

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

The status badge, logs, and button visibility automatically update every 3 seconds
while a job is running, and immediately after any action (start/cancel/restart).

**Managing the Computation:**

Depending on the current status, you'll see different control buttons:
- **Start Computation**: Begins the route calculation (shown when PENDING)
- **Cancel Computation**: Stops the running task immediately (shown when RUNNING)
- **Restart Computation**: Resets and restarts the job (shown when COMPLETED or FAILED)

Button visibility updates automatically as the job status changes.

**Worker Information:**

The Celery Worker Information panel shows details about the computation infrastructure:
- **Worker Availability**: Number of background workers available to process your job
- **Task Celery Status**: Internal task state from the Celery task queue
- **Worker Name**: Hostname of the specific worker processing your job

This information is fetched on page load and after starting/restarting a computation.
It helps diagnose issues if your job stays in PENDING state (no workers available)
or if you need to report problems to system administrators.

**Computation Logs:**

The logs section displays worker output as it becomes available. During RUNNING state,
logs update every 3 seconds via polling. Once the computation completes (COMPLETED or
FAILED status), the full worker logs are displayed, containing:
- Algorithm execution steps and progress
- Parameters used for the optimization
- Statistics about the generated route
- Any warnings or errors encountered

The logs are synced from the worker container after the job finishes.

# Notes (This section is for developer notes and will not appear in the user documentation.)

Page runs in split layout with map on left (shows data upload locations) and controls on right.
Uses Bootstrap-only styling (no custom CSS except whiteSpace for log wrapping).
Polling interval (3s) only active when job is RUNNING, automatically disabled when complete.
All control callbacks include status checks to prevent duplicate operations from multiple browser tabs.
Worker runs in separate Docker container, so real-time log streaming is not possible.
Celery worker info updates only on page load and after start/restart (performance optimization).
"""

import logging
from dash import html, register_page, callback, Input, Output, State, dcc, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.background_job_manager import get_background_job_manager
from cosmonaut_app.constants.general import (
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    LOADING_OVERLAY_SHARED_ID,
    START_BUTTON_ROUTE_COMPUTATION_ID,
    CANCEL_BUTTON_ROUTE_COMPUTATION_ID,
    RESTART_BUTTON_ROUTE_COMPUTATION_ID,
    NEXT_BUTTON_ROUTE_COMPUTATION_ID,
    STATUS_BADGE_ROUTE_COMPUTATION_ID,
    WORKER_STATUS_TEXT_ROUTE_COMPUTATION_ID,
    TASK_STATUS_TEXT_ROUTE_COMPUTATION_ID,
    WORKER_NAME_TEXT_ROUTE_COMPUTATION_ID,
    LOG_VIEWER_ROUTE_COMPUTATION_ID,
    STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID,
    UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID,
)
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    progress_footer,
    build_url_step,
    create_map,
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
        disabled=(status != JOB_STATUS_RUNNING),
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

    card_body = [
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
        dcc.Store(id=UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID, data=None),
    ]

    routing_params_path = build_url_step("routing_params", job_id)
    route_download_path = build_url_step("route_download", job_id)

    footer = progress_footer(
        prev_url=routing_params_path,
        next_url=route_download_path,
        next_id=NEXT_BUTTON_ROUTE_COMPUTATION_ID,
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
        dbc.Spinner(size="sm", spinner_class_name="ms-2")
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
    """Create control buttons based on current status.

    All buttons are always rendered to avoid callback errors.
    Visibility is controlled by the update_status callback via style property.
    Initial visibility is set based on status at page load.
    """
    # Start button (initially visible for PENDING or FAILED)
    start_button = dbc.Button(
        "Start Computation",
        id=START_BUTTON_ROUTE_COMPUTATION_ID,
        color="success",
        className="me-2",
        style={"display": "inline-block" if status == JOB_STATUS_PENDING else "none"},
    )

    # Cancel button (initially visible for RUNNING)
    cancel_button = dbc.Button(
        "Cancel Computation",
        id=CANCEL_BUTTON_ROUTE_COMPUTATION_ID,
        color="danger",
        className="me-2",
        style={"display": "inline-block" if status == JOB_STATUS_RUNNING else "none"},
    )

    # Restart button (initially visible for COMPLETED or FAILED)
    restart_button = dbc.Button(
        "Restart Computation",
        id=RESTART_BUTTON_ROUTE_COMPUTATION_ID,
        color="warning",
        className="me-2",
        style={
            "display": "inline-block"
            if status in [JOB_STATUS_COMPLETED, JOB_STATUS_FAILED]
            else "none"
        },
    )

    buttons = [start_button, cancel_button, restart_button]

    return html.Div(buttons, className="mb-3")


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
        className="mb-3",
    )


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(STATUS_BADGE_ROUTE_COMPUTATION_ID, "children"),
    Output(STATUS_BADGE_ROUTE_COMPUTATION_ID, "color"),
    Output(STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID, "disabled"),
    Output(LOG_VIEWER_ROUTE_COMPUTATION_ID, "children"),
    Output(NEXT_BUTTON_ROUTE_COMPUTATION_ID, "disabled"),
    Output(START_BUTTON_ROUTE_COMPUTATION_ID, "style"),
    Output(CANCEL_BUTTON_ROUTE_COMPUTATION_ID, "style"),
    Output(RESTART_BUTTON_ROUTE_COMPUTATION_ID, "style"),
    Input(STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID, "n_intervals"),
    Input(UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID, "data"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=False,
)
def update_status(n_intervals, trigger, job_id):
    """Poll job status and logs (lightweight, frequent updates).

    Also controls button visibility based on status changes.
    """
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

    # Enable next button only when completed
    next_button_disabled = status != JOB_STATUS_COMPLETED

    # Control button visibility based on status
    # Start button: visible for PENDING or FAILED
    start_style = {
        "display": "inline-block" if status == JOB_STATUS_PENDING else "none"
    }

    # Cancel button: visible for RUNNING
    cancel_style = {
        "display": "inline-block" if status == JOB_STATUS_RUNNING else "none"
    }

    # Restart button: visible for COMPLETED or FAILED
    restart_style = {
        "display": "inline-block"
        if status in [JOB_STATUS_COMPLETED, JOB_STATUS_FAILED]
        else "none"
    }

    # Get logs
    log_content = job.get_logs()

    return (
        status,
        color_map.get(status, "secondary"),
        disable_interval,
        log_content,
        next_button_disabled,
        start_style,
        cancel_style,
        restart_style,
    )


@callback(
    Output(WORKER_STATUS_TEXT_ROUTE_COMPUTATION_ID, "children"),
    Output(TASK_STATUS_TEXT_ROUTE_COMPUTATION_ID, "children"),
    Output(WORKER_NAME_TEXT_ROUTE_COMPUTATION_ID, "children"),
    Input(UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID, "data"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=False,
)
def update_celery_info(trigger, job_id):
    """Update Celery worker information (heavyweight, infrequent updates).

    Only executes on initial load (n_intervals == 0) or when trigger == "celery_check".
    """
    # Only execute on initial load or explicit celery check trigger
    logging.info(f"Updating Celery info for job {job_id}")

    job = CosmonautJob(job_id=job_id)

    # Get Celery worker information
    job_manager = get_background_job_manager()
    tasks_overview = job_manager.get_all_tasks_overview()

    # Check worker availability
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

    logging.info(
        f"Celery info for job {job_id}: Worker Status: {worker_status_text}, "
        f"Task Status: {task_status_text}, Worker Name: {worker_name_text}"
    )
    return (
        worker_status_text,
        task_status_text,
        worker_name_text,
    )


@callback(
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(START_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    Input(CANCEL_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    Input(RESTART_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    prevent_initial_call=True,
)
def show_loading(*inputs):
    """Show loading overlay when any action button is clicked."""
    return any(inp is not None for inp in inputs)


@callback(
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Output(STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID, "disabled", allow_duplicate=True),
    Output(UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID, "data", allow_duplicate=True),
    Input(START_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def start_computation(n_clicks, job_id):
    """Start the routing computation.

    Checks current status to prevent duplicate submissions (multiple tabs).
    Closes loading modal, enables polling interval, and triggers celery info update.
    """
    if n_clicks is None:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    current_status = job.get_status()

    # Prevent duplicate submission if already running
    if current_status == JOB_STATUS_RUNNING:
        logging.warning(f"Job {job_id} already running, ignoring start request")
        return False, no_update, no_update

    # Only start if PENDING or FAILED
    if current_status not in [JOB_STATUS_PENDING, JOB_STATUS_FAILED]:
        logging.warning(f"Cannot start job {job_id} with status {current_status}")
        return False, no_update, no_update

    job.submit()
    logging.info(f"Started computation for job {job_id}")

    # Close modal, enable interval, trigger celery check
    return False, False, "celery_check"


@callback(
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Output(UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID, "data", allow_duplicate=True),
    Input(CANCEL_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def cancel_computation(n_clicks, job_id):
    """Cancel the running computation.

    Checks current status to prevent duplicate cancellations (multiple tabs).
    Closes loading modal and triggers status update.
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
        return False, no_update

    if not job.model.celery_task_id:
        logging.warning(f"Job {job_id} has no celery_task_id to cancel")
        return False, no_update

    job_manager = get_background_job_manager()
    job_manager.revoke_job(job.model.celery_task_id, terminate=True)
    logging.info(f"Cancelled computation for job {job_id}")

    # Close modal, trigger status check
    return False, "status_check"


@callback(
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Output(STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID, "disabled", allow_duplicate=True),
    Output(UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID, "data", allow_duplicate=True),
    Input(RESTART_BUTTON_ROUTE_COMPUTATION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def restart_computation(n_clicks, job_id):
    """Restart the computation (cancel if running, then start).

    Checks current status to handle edge cases (multiple tabs).
    Closes loading modal, enables polling interval, and triggers celery info update.
    """
    if n_clicks is None:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    current_status = job.get_status()

    # If currently running, don't restart (user should cancel first)
    if current_status == JOB_STATUS_RUNNING:
        logging.warning(f"Job {job_id} is running, cannot restart. Cancel first.")
        return False, no_update, no_update

    # Cancel existing task if it exists (safety check)
    if job.model.celery_task_id:
        job_manager = get_background_job_manager()
        job_manager.revoke_job(job.model.celery_task_id, terminate=True)

    job.reset()
    job.submit()

    logging.info(f"Restarted computation for job {job_id}")

    # Close modal, enable interval, trigger celery check
    return False, False, "celery_check"
