"""Worker Management Page for COSMONAUT App.

This page provides real-time monitoring and control of Celery background workers.
Allows viewing active, reserved, scheduled, and revoked tasks, as well as killing
or cancelling tasks.
"""

import logging
from datetime import datetime

import dash_bootstrap_components as dbc
from dash import callback, callback_context, html, register_page
from dash.dash_table import DataTable
from dash.dependencies import Input, Output, State

from cosmonaut_app.constants.html_ids import (
    ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID,
    WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_CANCEL_MODAL_CANCEL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_CANCEL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID,
    WORKER_CANCEL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID,
    WORKER_CANCEL_MODAL_WORKER_MANAGEMENT_ID,
    WORKER_KILL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_KILL_MODAL_CANCEL_BTN_WORKER_MANAGEMENT_ID,
    WORKER_KILL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID,
    WORKER_KILL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID,
    WORKER_KILL_MODAL_WORKER_MANAGEMENT_ID,
    WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID,
    WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
    WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID,
    WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID,
)
from cosmonaut_app.layout import create_header, page_container_fullscreen_layout

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

    Returns:
        dbc.Card: Section component
    """
    table = create_task_datatable(table_id, columns, selectable)

    section_content = [
        html.H4(title, className="mb-2"),
        html.P(description, className="text-muted mb-3"),
        table,
    ]

    if button_id and button_label:
        button = dbc.Button(
            button_label,
            id=button_id,
            color="danger" if "Kill" in button_label else "warning",
            className="mt-3",
            disabled=True,  # Initially disabled
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
    if not start_timestamp:
        return "N/A"

    try:
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
    except (ValueError, TypeError):
        return "N/A"


def extract_job_id_from_task(task):
    """Extract job_id from task args if it's a routing task.

    Args:
        task: Task dict from Celery inspect

    Returns:
        str: Job ID or "N/A"
    """
    try:
        # Task args is a list: [job_id, ...] for routing tasks
        args = task.get("args", [])
        if args and len(args) > 0:
            # First arg is typically job_id for our routing tasks
            return str(args[0])
    except (KeyError, IndexError, TypeError):
        pass
    return "N/A"


def format_active_tasks(active_tasks):
    """Format active tasks for display.

    Args:
        active_tasks: List of active task dicts from Celery

    Returns:
        list: Formatted task dicts
    """
    formatted = []
    for task in active_tasks:
        formatted.append(
            {
                "task_id": task.get("id", "N/A"),
                "task_name": task.get("name", "N/A").split(".")[-1],
                "worker": task.get("worker", "N/A"),
                "start_time": datetime.fromtimestamp(
                    task.get("time_start", 0)
                ).strftime("%H:%M:%S")
                if task.get("time_start")
                else "N/A",
                "duration": format_duration(task.get("time_start")),
                "job_id": extract_job_id_from_task(task),
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
        delivery_info = task.get("delivery_info", {})
        queue = delivery_info.get("routing_key", "default")

        formatted.append(
            {
                "task_id": task.get("id", "N/A"),
                "task_name": task.get("name", "N/A").split(".")[-1],
                "queue": queue,
                "worker": task.get("worker", "N/A"),
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
        eta = task.get("eta")
        if eta:
            try:
                eta_str = datetime.fromisoformat(eta.replace("Z", "+00:00")).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, AttributeError):
                eta_str = str(eta)
        else:
            eta_str = "N/A"

        # Extract queue
        delivery_info = task.get("delivery_info", {})
        queue = delivery_info.get("routing_key", "default")

        formatted.append(
            {
                "task_id": task.get("id", "N/A"),
                "task_name": task.get("name", "N/A").split(".")[-1],
                "eta": eta_str,
                "queue": queue,
            }
        )
    return formatted


def format_revoked_tasks(revoked_ids, job_manager):
    """Format revoked tasks for display.

    Args:
        revoked_ids: List of revoked task IDs
        job_manager: BackgroundJobManager instance

    Returns:
        list: Formatted task dicts
    """
    formatted = []
    for task_id in revoked_ids:
        # Try to get task info from result backend
        try:
            task_info = job_manager.get_job_status(task_id)
            task_name = "Unknown"
            status = task_info.get("status", "REVOKED")

            # Try to extract more info if available
            if task_info.get("result"):
                result = task_info["result"]
                if isinstance(result, dict) and "task_name" in result:
                    task_name = result["task_name"]
        except Exception:
            task_name = "Unknown"
            status = "REVOKED"

        formatted.append(
            {
                "task_id": task_id,
                "task_name": task_name,
                "worker": "N/A",
                "status": status,
            }
        )
    return formatted


def format_worker_stats(overview):
    """Format worker statistics as cards.

    Args:
        overview: Task overview dict

    Returns:
        list: List of dbc.Card components
    """
    workers = overview.get("workers", [])
    active_tasks = overview.get("active", [])
    reserved_tasks = overview.get("reserved", [])
    scheduled_tasks = overview.get("scheduled", [])

    if not workers:
        return []

    cards = []
    for worker in workers:
        # Count tasks for this worker
        active_count = sum(1 for task in active_tasks if task.get("worker") == worker)
        reserved_count = sum(
            1 for task in reserved_tasks if task.get("worker") == worker
        )
        scheduled_count = sum(
            1 for task in scheduled_tasks if task.get("worker") == worker
        )

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
            style={"backgroundColor": "rgb(240, 248, 255)"},
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
                        "Refresh",
                        id=WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID,
                        color="primary",
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
        columns=["task_id", "task_name", "worker", "status"],
        selectable=False,
    )

    # Kill modal
    kill_modal = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Confirm Task Termination")),
            dbc.ModalBody(
                [
                    html.P("⚠️ Warning: This will send SIGTERM to the worker process."),
                    html.Pre(
                        id=WORKER_KILL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID,
                        className="bg-light p-3 rounded",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel",
                        id=WORKER_KILL_MODAL_CANCEL_BTN_WORKER_MANAGEMENT_ID,
                        color="secondary",
                    ),
                    dbc.Button(
                        "Kill Task",
                        id=WORKER_KILL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID,
                        color="danger",
                    ),
                ]
            ),
        ],
        id=WORKER_KILL_MODAL_WORKER_MANAGEMENT_ID,
        is_open=False,
    )

    # Cancel modal
    cancel_modal = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Confirm Task Cancellation")),
            dbc.ModalBody(
                [
                    html.P(
                        "This will prevent the task from executing. Running tasks will continue."
                    ),
                    html.Pre(
                        id=WORKER_CANCEL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID,
                        className="bg-light p-3 rounded",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel",
                        id=WORKER_CANCEL_MODAL_CANCEL_BTN_WORKER_MANAGEMENT_ID,
                        color="secondary",
                    ),
                    dbc.Button(
                        "Confirm Cancellation",
                        id=WORKER_CANCEL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID,
                        color="warning",
                    ),
                ]
            ),
        ],
        id=WORKER_CANCEL_MODAL_WORKER_MANAGEMENT_ID,
        is_open=False,
    )

    # Dummy component for triggering updates
    dummy = html.Div(
        id=WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
        style={"display": "none"},
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
            kill_modal,
            cancel_modal,
            dummy,
        ],
        className="my-4",
        fluid=True,
    )

    return page_container_fullscreen_layout([header, page_content])


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    Output(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    Output(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    Output(REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    Output(WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID, "children"),
    Output(WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID, "children"),
    Input(WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    Input(WORKER_KILL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    Input(WORKER_CANCEL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    prevent_initial_call=False,  # Load on page load
)
def refresh_worker_data(refresh_clicks, kill_clicks, cancel_clicks):
    """Fetch and display current worker and task data."""
    from cosmonaut_app.background_job_manager import get_background_job_manager

    try:
        job_manager = get_background_job_manager()

        # Get task overview from Celery
        overview = job_manager.get_all_tasks_overview()

        # Check if workers are available
        if not overview.get("workers"):
            # Return empty data with error message
            error_msg = html.Div(
                "⚠️ No Celery workers are currently running. Please start the worker service.",
                className="alert alert-warning",
            )
            return [], [], [], [], error_msg, "Last refresh: Never"

        # Format data for each table
        active_data = format_active_tasks(overview.get("active", []))
        reserved_data = format_reserved_tasks(overview.get("reserved", []))
        scheduled_data = format_scheduled_tasks(overview.get("scheduled", []))
        revoked_data = format_revoked_tasks(overview.get("revoked", []), job_manager)

        # Create worker stats cards
        worker_cards = format_worker_stats(overview)

        # Update timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        timestamp_text = f"Last refresh: {timestamp}"

        log.info(
            f"Worker data refreshed - {len(active_data)} active, "
            f"{len(reserved_data)} reserved, {len(scheduled_data)} scheduled, "
            f"{len(revoked_data)} revoked tasks"
        )

        return (
            active_data,
            reserved_data,
            scheduled_data,
            revoked_data,
            worker_cards,
            timestamp_text,
        )

    except Exception as e:
        log.error(f"Error fetching worker data: {str(e)}", exc_info=True)
        error_msg = html.Div(
            f"⚠️ Error fetching worker data: {str(e)}", className="alert alert-danger"
        )
        return [], [], [], [], error_msg, "Last refresh: Error"


@callback(
    Output(WORKER_KILL_BTN_WORKER_MANAGEMENT_ID, "disabled"),
    Input(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
)
def toggle_kill_button(selected_rows):
    """Enable kill button only when a task is selected."""
    return not selected_rows or len(selected_rows) == 0


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
    Output(WORKER_KILL_MODAL_WORKER_MANAGEMENT_ID, "is_open"),
    Output(WORKER_KILL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID, "children"),
    Input(WORKER_KILL_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    Input(WORKER_KILL_MODAL_CANCEL_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    State(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    prevent_initial_call=True,
)
def manage_kill_modal(kill_clicks, cancel_clicks, selected_rows, table_data):
    """Open/close kill confirmation modal."""
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    if triggered_id == WORKER_KILL_BTN_WORKER_MANAGEMENT_ID and selected_rows:
        # Open modal with task info
        task = table_data[selected_rows[0]]
        task_info = f"""Task: {task['task_name']}
ID: {task['task_id']}
Worker: {task['worker']}
Duration: {task['duration']}"""
        return True, task_info

    # Close modal
    return False, ""


@callback(
    Output(WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID, "children"),
    Input(WORKER_KILL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    State(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    prevent_initial_call=True,
)
def confirm_kill_task(confirm_clicks, selected_rows, table_data):
    """Kill the selected task."""
    from cosmonaut_app.background_job_manager import get_background_job_manager

    if selected_rows:
        task = table_data[selected_rows[0]]
        task_id = task["task_id"]

        job_manager = get_background_job_manager()
        job_manager.revoke_job(task_id, terminate=True)  # SIGTERM

        log.warning(f"Task {task_id} ({task['task_name']}) killed by user")

    return None  # Triggers refresh via callback 1


@callback(
    Output(WORKER_CANCEL_MODAL_WORKER_MANAGEMENT_ID, "is_open"),
    Output(WORKER_CANCEL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID, "children"),
    Input(WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    Input(WORKER_CANCEL_MODAL_CANCEL_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    State(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    State(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    prevent_initial_call=True,
)
def manage_cancel_modal(
    cancel_clicks,
    modal_cancel_clicks,
    reserved_selected,
    reserved_data,
    scheduled_selected,
    scheduled_data,
):
    """Open/close cancel confirmation modal."""
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    if triggered_id == WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID:
        # Determine which table has selection
        if reserved_selected and len(reserved_selected) > 0:
            task = reserved_data[reserved_selected[0]]
        elif scheduled_selected and len(scheduled_selected) > 0:
            task = scheduled_data[scheduled_selected[0]]
        else:
            return False, ""

        task_info = f"""Task: {task['task_name']}
ID: {task['task_id']}
Queue: {task.get('queue', 'default')}"""
        return True, task_info

    # Close modal
    return False, ""


@callback(
    Output(
        WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID,
        "children",
        allow_duplicate=True,
    ),
    Input(WORKER_CANCEL_MODAL_CONFIRM_BTN_WORKER_MANAGEMENT_ID, "n_clicks"),
    State(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    State(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "selected_rows"),
    State(SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID, "data"),
    prevent_initial_call=True,
)
def confirm_cancel_task(
    confirm_clicks, reserved_selected, reserved_data, scheduled_selected, scheduled_data
):
    """Cancel the selected task."""
    from cosmonaut_app.background_job_manager import get_background_job_manager

    # Determine which table has selection
    if reserved_selected and len(reserved_selected) > 0:
        task = reserved_data[reserved_selected[0]]
    elif scheduled_selected and len(scheduled_selected) > 0:
        task = scheduled_data[scheduled_selected[0]]
    else:
        return None

    task_id = task["task_id"]

    job_manager = get_background_job_manager()
    job_manager.revoke_job(task_id, terminate=False)  # Revoke only

    log.warning(f"Task {task_id} ({task['task_name']}) cancelled by user")

    return None  # Triggers refresh via callback 1
