"""View and filter application logs for debugging and monitoring.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This page provides access to the application's logging system, allowing you to track
system activity, debug issues, and monitor operations. You can:

- Filter logs by date and time range
- Select specific log levels (Debug, Info, Warning, Error, Critical)
- Filter by process ID to track specific server processes
- View logs in a formatted, readable table
- Refresh logs on demand to see latest entries

Logs are stored in the database and include timestamps, log levels, logger names,
and messages. This is the primary tool for understanding system behavior, diagnosing
problems, and monitoring application execution.

# Notes (This section is for developer notes and will not appear in the user documentation.)

This page is publicly accessible without authentication.
"""

import datetime

import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html, register_page

from cosmonaut_app.constants.html_ids import (
    END_HOUR_INPUT_LOGS_ID,
    END_MINUTE_INPUT_LOGS_ID,
    LOG_DATE_PICKER_LOGS_ID,
    LOG_LEVELS_DROPDOWN_LOGS_ID,
    LOG_OUTPUT_DIV_LOGS_ID,
    LOG_PID_INPUT_LOGS_ID,
    PID_CHECKLIST_LOGS_ID,
    START_HOUR_INPUT_LOGS_ID,
    START_MINUTE_INPUT_LOGS_ID,
    TIME_ERROR_DIV_LOGS_ID,
    TIME_INPUT_GROUP_LOGS_ID,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.layout import create_header, page_container_column_layout
from cosmonaut_app.logs_table import format_logs_list

register_page(
    __name__,
    path="/logs",
    name="Logs",
    title="COSMONAUT - Logs",
    description="View application logs for debugging and monitoring.",
)


def layout():
    """Dynamic layout that calculates current time on each page visit."""
    # Calculate time values dynamically
    now = datetime.datetime.now()
    start_hour = now.hour - 1 if now.hour > 0 else 23
    start_minute = now.minute
    end_hour = now.hour
    end_minute = now.minute

    header = create_header(
        "View logs", "Show logs of the webserver", bg_color="bg-info", rounded=False
    )

    # UI Components
    date_selector = [
        html.Label("Select Date"),
        html.Br(),
        dcc.DatePickerSingle(
            id=LOG_DATE_PICKER_LOGS_ID,
            date=now.date(),
        ),
    ]

    time_selector = [
        html.Label("Time Range"),
        html.Div(
            children=[
                dbc.InputGroup(
                    [
                        dbc.InputGroupText("From"),
                        dbc.Input(
                            id=START_HOUR_INPUT_LOGS_ID,
                            type="number",
                            value=start_hour,
                            min=0,
                            max=23,
                        ),
                        dbc.InputGroupText(":"),
                        dbc.Input(
                            id=START_MINUTE_INPUT_LOGS_ID,
                            type="number",
                            value=start_minute,
                            min=0,
                            max=59,
                        ),
                        dbc.InputGroupText("To"),
                        dbc.Input(
                            id=END_HOUR_INPUT_LOGS_ID,
                            type="number",
                            value=end_hour,
                            min=0,
                            max=23,
                        ),
                        dbc.InputGroupText(":"),
                        dbc.Input(
                            id=END_MINUTE_INPUT_LOGS_ID,
                            type="number",
                            value=end_minute,
                            min=0,
                            max=59,
                        ),
                    ],
                    id=TIME_INPUT_GROUP_LOGS_ID,
                ),
                html.Small(id=TIME_ERROR_DIV_LOGS_ID, className="text-danger"),
            ],
        ),
    ]

    log_levels = [
        html.Label("Log Levels"),
        dcc.Dropdown(
            id=LOG_LEVELS_DROPDOWN_LOGS_ID,
            options=[
                {"label": "Debug", "value": "DEBUG"},
                {"label": "Info", "value": "INFO"},
                {"label": "Warning", "value": "WARNING"},
                {"label": "Error", "value": "ERROR"},
                {"label": "Critical", "value": "CRITICAL"},
            ],
            value=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            multi=True,
        ),
    ]

    pid_selector = [
        html.Label("PID"),
        dbc.InputGroup(
            [
                dbc.InputGroupText(
                    dbc.Checklist(
                        id=PID_CHECKLIST_LOGS_ID,
                        options=[{"label": "Filter by PID", "value": "on"}],
                        value=[],
                        switch=True,
                    ),
                ),
                dbc.Input(
                    id=LOG_PID_INPUT_LOGS_ID,
                    type="number",
                    placeholder="Process ID",
                    disabled=True,
                ),
            ],
        ),
    ]

    page_layout = [
        header,
        dbc.Container(
            [
                dbc.Row(
                    [dbc.Col(date_selector, width=6), dbc.Col(time_selector, width=6)],
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(log_levels, width=4),
                        dbc.Col(pid_selector, width=4),
                    ],
                    className="mb-4",
                ),
                html.Div(
                    id=LOG_OUTPUT_DIV_LOGS_ID,
                    children="Logs will appear here...",
                    className="border p-3 bg-light rounded",
                    style={"maxHeight": "70vh", "overflowY": "auto"},
                ),
            ],
            className="my-4",
        ),
    ]

    return page_container_column_layout(page_layout)


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(LOG_OUTPUT_DIV_LOGS_ID, "children"),
    Output(LOG_PID_INPUT_LOGS_ID, "disabled"),
    Output(TIME_ERROR_DIV_LOGS_ID, "children"),
    Output(TIME_INPUT_GROUP_LOGS_ID, "className"),
    Input(LOG_DATE_PICKER_LOGS_ID, "date"),
    Input(START_HOUR_INPUT_LOGS_ID, "value"),
    Input(START_MINUTE_INPUT_LOGS_ID, "value"),
    Input(END_HOUR_INPUT_LOGS_ID, "value"),
    Input(END_MINUTE_INPUT_LOGS_ID, "value"),
    Input(LOG_LEVELS_DROPDOWN_LOGS_ID, "value"),
    Input(PID_CHECKLIST_LOGS_ID, "value"),
    Input(LOG_PID_INPUT_LOGS_ID, "value"),
)
def log_manager(date, sh, sm, eh, em, levels, pid_checklist, pid):
    """Manage and display logs based on user input."""
    # Disable PID input when checkbox is not checked
    disabled_pid = "on" not in pid_checklist

    # Handle PID selection
    if disabled_pid:
        pid = None

    # Validate time inputs
    bad_values_log = "Select a valid time range."
    bad_input_group_class = "border border-danger rounded"

    if None in (sh, sm, eh, em):
        error_msg = "All time fields must be filled."
        return bad_values_log, disabled_pid, error_msg, bad_input_group_class

    if (sh, sm) >= (eh, em):
        error_msg = "Start time must be before end time."
        return bad_values_log, disabled_pid, error_msg, bad_input_group_class

    # Query logs
    logs = DataBaseManager.query_logs(date, sh, sm, eh, em, levels, pid)

    if not logs:
        return "No logs found for the selected criteria.", disabled_pid, "", ""

    log_formatted = format_logs_list(logs, show_pid=True)

    return log_formatted, disabled_pid, "", ""
