"""Worker Management Page for COSMONAUT App.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This page provides real-time monitoring and control of Celery background workers.
Allows viewing active, reserved, scheduled, and revoked tasks, as well as killing
or cancelling tasks.

# Notes (This section is for developer notes and will not appear in the user documentation.)

No additional developer notes for this page.
"""

import logging
from datetime import datetime
import re

import dash
import dash_bootstrap_components as dbc
from dash import callback, html, no_update, register_page
from dash.exceptions import PreventUpdate
from dash.dash_table import DataTable
from dash.dependencies import Input, Output, State
from celery.result import AsyncResult

from cosmonaut_app.constants.html_ids import (
    ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    LOADING_OVERLAY_SHARED_ID,
    RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID,
    TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID,
    WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_KILL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID,
    WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
    WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID,
    WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID,
)
from cosmonaut_app.layout import create_header, page_container_column_layout
from cosmonaut_app.background_job_manager import (
    background_job_manager,
    NAME_ROUTING_TASK,
    BackgroundJobManager,
)
from cosmonaut_app.error_handling import WrongCeleryTaskId


log = logging.getLogger(__name__)

register_page(
    __name__,
    path="/worker-management",
    name="Worker Management",
    title="COSMONAUT - Worker Management",
    description="Monitor and control Celery background workers and tasks.",
)


# ============================================================================
# Factory Functions (Reusable Components)
# ============================================================================


def create_task_datatable(table_id, columns, selectable=False):
    """Create a consistently styled DataTable.

    Args:
        table_id: HTML ID for the table
        columns: List of column names
        selectable: Whether to enable row selection

    Returns:
        DataTable: Configured DataTable component
    """
    column_defs = []
    for col in columns:
        col_def = {"name": col.replace("_", " ").title(), "id": col}
        # Monospace font for task_id column
        if col == "task_id":
            col_def["presentation"] = "markdown"
        column_defs.append(col_def)

    # style needed: Dash DataTable uses its own style_* API, not className
    table_style = {
        "cell": {"padding": "8px"},
        "header": {
            "backgroundColor": "rgb(230, 230, 230)",
            "fontWeight": "bold",
            "padding": "8px",
        },
        "data": {
            "whiteSpace": "normal",
            "height": "auto",
        },
    }

    row_selectable = "single" if selectable else False

    return DataTable(
        id=table_id,
        columns=column_defs,
        data=[],
        page_size=10,
        style_cell=table_style["cell"],
        style_header=table_style["header"],
        style_data=table_style["data"],
        style_data_conditional=[
            {
                "if": {"column_id": "task_id"},
                "fontFamily": "monospace",
                "fontSize": "12px",
            },
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "rgb(248, 248, 248)",
            },
        ],
        row_selectable=row_selectable,
    )


def create_task_section(
    title,
    description,
    table_id,
    columns,
    button_id=None,
    button_label=None,
    selectable=False,
    task_id_input_id=None,
    initially_disabled=True,
):
    """Create a task section with title, description, table, and optional button.

    Args:
        title: Section title
        description: Section description
        table_id: ID for the DataTable
        columns: List of column names
        button_id: Optional button ID
        button_label: Optional button label
        selectable: Whether table rows are selectable
        task_id_input_id: Optional input field ID for selected task ID
        initially_disabled: Whether button is initially disabled

    Returns:
        dbc.Card: Section component
    """
    table = create_task_datatable(table_id, columns, selectable)

    section_content = [
        html.H4(title, className="mb-2"),
        html.P(description, className="text-muted mb-3"),
        table,
    ]

    if task_id_input_id:
        task_id_input = dbc.Input(
            id=task_id_input_id,  # nocheck
            placeholder="Select a task from the table above or enter task ID",
            className="mt-3",
        )
        section_content.append(task_id_input)

    if button_id and button_label:
        button = dbc.Button(
            button_label,
            id=button_id,  # nocheck
            color="danger" if "Kill" in button_label else "warning",
            className="mt-3",
            disabled=initially_disabled,
        )
        section_content.append(button)

    return dbc.Card(
        dbc.CardBody(section_content),
        className="mb-4",
    )


# ============================================================================
# Data Formatting Functions
# ============================================================================


def format_duration(start_timestamp):
    """Convert Unix timestamp to human-readable duration.

    Args:
        start_timestamp: Unix timestamp of task start

    Returns:
        str: Duration in format like "2m 30s" or "1h 15m"
    """
    duration_seconds = int(datetime.now().timestamp() - start_timestamp)
    if duration_seconds < 60:
        return f"{duration_seconds}s"
    elif duration_seconds < 3600:
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def format_active_tasks(active_tasks):
    """Format active tasks for display.

    Args:
        active_tasks: List of active task dicts from Celery

    Returns:
        list: Formatted task dicts
    """
    formatted = []
    for task in active_tasks:
        if task["name"] == NAME_ROUTING_TASK:
            job_id = str(task["args"][0])
        else:
            job_id = "N/A"
        formatted.append(
            {
                "task_id": task["id"],
                "task_name": task["name"].split(".")[-1],
                "worker": task["worker"],
                "start_time": datetime.fromtimestamp(task["time_start"]).strftime(
                    "%H:%M:%S"
                ),
                "duration": format_duration(task["time_start"]),
                "job_id": job_id,
            }
        )
    return formatted


def format_reserved_tasks(reserved_tasks):
    """Format reserved tasks for display.

    Args:
        reserved_tasks: List of reserved task dicts

    Returns:
        list: Formatted task dicts
    """
    formatted = []
    for task in reserved_tasks:
        # Extract queue from delivery_info
        delivery_info = task["delivery_info"]
        queue = delivery_info["routing_key"]

        formatted.append(
            {
                "task_id": task["id"],
                "task_name": task["name"].split(".")[-1],
                "queue": queue,
                "worker": task["worker"],
            }
        )
    return formatted


def format_scheduled_tasks(scheduled_tasks):
    """Format scheduled tasks for display.

    Args:
        scheduled_tasks: List of scheduled task dicts

    Returns:
        list: Formatted task dicts
    """
    formatted = []
    for task in scheduled_tasks:
        # ETA is in task dict
        eta_str = datetime.fromisoformat(task["eta"].replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Extract queue
        delivery_info = task["delivery_info"]
        queue = delivery_info["routing_key"]

        formatted.append(
            {
                "task_id": task["id"],
                "task_name": task["name"].split(".")[-1],
                "eta": eta_str,
                "queue": queue,
            }
        )
    return formatted


def format_revoked_tasks(revoked_list: list, job_manager: BackgroundJobManager):
    """Format revoked tasks for DataTable display with enrichment from result backend.

    Args:
        revoked_list: List of revoked task IDs (strings)
        job_manager: BackgroundJobManager instance for accessing Celery app

    Returns:
        list: List of task dictionaries formatted for table
    """
    tasks = []
    for task_id in revoked_list:
        # Get AsyncResult to access task status
        result = AsyncResult(task_id, app=background_job_manager.app)
        log.debug(f"Revoked task {task_id} has status {result.status}")
        log.debug(result)

        # Get task name from Redis (stored at submission time)
        try:
            task_name_full = background_job_manager.app.backend.client.get(
                f"task_name:{task_id}"
            ).decode()
            task_name = task_name_full.split(".")[-1]
        except AttributeError:
            log.warning(f"Task name not found in Redis for revoked task {task_id}")
            task_name = "Unknown"

        tasks.append(
            {
                "task_id": task_id,
                "task_name": task_name,
                "status": result.status,
            }
        )
    return tasks


def format_worker_stats(overview):
    """Format worker statistics as cards.

    Args:
        overview: Task overview dict

    Returns:
        list: List of dbc.Card components
    """
    workers = overview["workers"]
    active_tasks = overview["active"]
    reserved_tasks = overview["reserved"]
    scheduled_tasks = overview["scheduled"]

    if not workers:
        return []

    cards = []
    for worker in workers:
        # Count tasks for this worker
        active_count = sum(1 for task in active_tasks if task["worker"] == worker)
        reserved_count = sum(1 for task in reserved_tasks if task["worker"] == worker)
        scheduled_count = sum(1 for task in scheduled_tasks if task["worker"] == worker)

        card = dbc.Card(
            dbc.CardBody(
                [
                    html.H5(worker, className="card-title"),
                    html.P(
                        [
                            f"Active: {active_count} | ",
                            f"Reserved: {reserved_count} | ",
                            f"Scheduled: {scheduled_count}",
                        ],
                        className="card-text",
                    ),
                ]
            ),
            className="mb-2",
            color="primary",
            outline=True,
        )
        cards.append(card)

    return cards


# ============================================================================
# Layout
# ============================================================================


def layout():
    """Create the worker management page layout."""
    # Header
    header = create_header(
        "Worker Management",
        "Monitor and control Celery background workers",
        bg_color="bg-info",
        rounded=False,
    )

    # Refresh controls
    refresh_controls = dbc.Row(
        [
            dbc.Col(
                [
                    dbc.Button(
                        [
                            html.I(className="bi bi-arrow-clockwise me-1"),
                            "Refresh",
                        ],
                        id=WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID,
                        color="primary",
                        className="me-2",
                    ),
                    dbc.Button(
                        [
                            html.I(className="bi bi-play me-1"),
                            "Submit Test Task",
                        ],
                        id=TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID,
                        color="success",
                        className="me-2",
                    ),
                    html.Span(
                        "Last refresh: Never",
                        id=WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID,
                    ),
                ]
            )
        ],
        className="mb-4",
    )

    # Worker stats cards (initially empty, populated by callback)
    worker_stats = html.Div(
        id=WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID, className="mb-4"
    )

    # Active tasks section
    active_section = create_task_section(
        title="Active Tasks",
        description="Currently running tasks on workers",
        table_id=ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID,
        columns=["task_id", "task_name", "worker", "start_time", "duration", "job_id"],
        button_id=WORKER_KILL_BTN_WORKER_MANAGEMENT_ID,
        button_label="Kill Selected Task",
        selectable=True,
        task_id_input_id=SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID,
        initially_disabled=False,
    )

    # Reserved tasks section
    reserved_section = create_task_section(
        title="Reserved Tasks",
        description="Tasks claimed by workers but not yet started",
        table_id=RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
        columns=["task_id", "task_name", "queue", "worker"],
        selectable=True,
    )

    # Scheduled tasks section
    scheduled_section = create_task_section(
        title="Scheduled Tasks",
        description="Tasks scheduled for future execution",
        table_id=SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
        columns=["task_id", "task_name", "eta", "queue"],
        button_id=WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID,
        button_label="Cancel Selected Task",
        selectable=True,
    )

    # Revoked tasks section
    revoked_section = create_task_section(
        title="Revoked Tasks",
        description="Cancelled or killed tasks",
        table_id=REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
        columns=["task_id", "task_name", "status"],
        selectable=False,
    )

    # Dummy component for triggering updates
    dummy = html.Div(
        id=WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
        className="d-none",
    )

    # Assemble page layout
    page_content = dbc.Container(
        [
            refresh_controls,
            worker_stats,
            active_section,
            reserved_section,
            scheduled_section,
            revoked_section,
            dummy,
        ],
        className="my-4",
        fluid=True,
    )

    return page_container_column_layout([header, page_content])


# ============================================================================
# Callbacks
# ============================================================================


# Clientside: open overlay instantly in the browser, avoiding server-side
# callback ordering issues with allow_duplicate.
dash.clientside_callback(
    "function(n) { return true; }",
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    prevent_initial_call=True,
)


@callback(
    output={
        "active_data": Output(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
        "reserved_data": Output(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
        "scheduled_data": Output(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
        "revoked_data": Output(REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
        "worker_cards": Output(WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID, "children"),
        "last_refresh": Output(
            WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID, "children"
        ),
        "loading": Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
        "active_selected": Output(
            ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"
        ),
        "reserved_selected": Output(
            RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"
        ),
        "scheduled_selected": Output(
            SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"
        ),
    },
    inputs={
        "refresh_clicks": Input(WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
        "dummy_data": Input(
            WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID, "children"
        ),
    },
    prevent_initial_call="initial_duplicate",
)
def refresh_worker_data(refresh_clicks, dummy_data):
    """Fetch and display current worker and task data."""
    log.info("Refreshing worker data")

    overview = background_job_manager.get_all_tasks_overview()
    log.debug(f"Retrieved task overview: {overview}")

    active_data = format_active_tasks(overview["active"])
    reserved_data = format_reserved_tasks(overview["reserved"])
    scheduled_data = format_scheduled_tasks(overview["scheduled"])
    revoked_data = format_revoked_tasks(overview["revoked"], background_job_manager)

    worker_cards = format_worker_stats(overview)

    timestamp = datetime.now().strftime("%H:%M:%S")

    log.info(
        f"Worker data refreshed - {len(active_data)} active, "
        f"{len(reserved_data)} reserved, {len(scheduled_data)} scheduled, "
        f"{len(revoked_data)} revoked tasks"
    )

    return {
        "active_data": active_data,
        "reserved_data": reserved_data,
        "scheduled_data": scheduled_data,
        "revoked_data": revoked_data,
        "worker_cards": worker_cards,
        "last_refresh": f"Last refresh: {timestamp}",
        "loading": False,
        "active_selected": [],
        "reserved_selected": [],
        "scheduled_selected": [],
    }


@callback(
    Output(SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID, "value"),
    Input(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
)
def update_selected_task_id(selected_rows, table_data):
    """Copy task ID from selected row to input field."""
    if selected_rows and len(selected_rows) > 0 and table_data:
        row_index = selected_rows[0]
        if row_index < len(table_data):
            task_id = table_data[row_index]["task_id"]
            return task_id
    return no_update


@callback(
    Output(WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID, "disabled"),
    Input(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    Input(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
)
def toggle_cancel_button(reserved_selected, scheduled_selected):
    """Enable cancel button when reserved or scheduled task selected."""
    has_selection = (reserved_selected and len(reserved_selected) > 0) or (
        scheduled_selected and len(scheduled_selected) > 0
    )
    return not has_selection


@callback(
    Output(WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID, "children"),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(WORKER_KILL_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    State(SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID, "value"),
    prevent_initial_call=True,
)
def confirm_kill_task(n_clicks, task_id):
    """Kill the task specified in the input field."""
    if task_id:
        # Validate UUID format: 8-4-4-4-12 hex digits
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, task_id, re.IGNORECASE):
            raise WrongCeleryTaskId(task_id)

        background_job_manager.revoke_job(task_id, terminate=True)  # SIGTERM

        log.warning(f"Task {task_id} killed by user")

    return None, True  # Triggers refresh via callback and opens overlay


@callback(
    Output(
        WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
        "children",
        allow_duplicate=True,
    ),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    State(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    State(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    prevent_initial_call=True,
)
def confirm_cancel_task(
    n_clicks, reserved_selected, reserved_data, scheduled_selected, scheduled_data
):
    """Cancel the selected task."""
    # Determine which table has selection
    if (
        reserved_selected
        and reserved_data
        and len(reserved_data) > reserved_selected[0]
    ):
        task = reserved_data[reserved_selected[0]]
    elif (
        scheduled_selected
        and scheduled_data
        and len(scheduled_data) > scheduled_selected[0]
    ):
        task = scheduled_data[scheduled_selected[0]]
    else:
        return None, False

    task_id = task["task_id"]

    background_job_manager.revoke_job(task_id, terminate=False)  # Revoke only

    log.warning(f"Task {task_id} ({task['task_name']}) cancelled by user")

    return None, True  # Triggers refresh via callback and opens overlay


@callback(
    Output(
        WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
        "children",
        allow_duplicate=True,
    ),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID, "n_clicks"),
    prevent_initial_call=True,
)
def submit_test_task(n_clicks):
    """Submit a test sleep task when button is clicked."""
    log.info("Test task button clicked")
    if n_clicks is None:
        raise PreventUpdate

    task_id, failed = background_job_manager.submit_test_task()

    if failed:
        log.error("Failed to submit test task")
    else:
        log.info(f"Test task submitted successfully with task_id={task_id}")

    return None, True  # Triggers refresh via dummy component and opens overlay
