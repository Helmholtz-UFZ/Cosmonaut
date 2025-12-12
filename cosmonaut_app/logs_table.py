"""Shared logs table component for displaying logs."""

import dash_bootstrap_components as dbc
from dash import html


def level_badge(level: str) -> dbc.Badge:
    """Format log level with color-coded badge."""
    color_map = {
        "DEBUG": "secondary",
        "INFO": "info",
        "WARNING": "warning",
        "ERROR": "danger",
        "CRITICAL": "dark",
    }
    return dbc.Badge(level, color=color_map.get(level, "primary"), className="me-1")


def format_logs_list(logs: list, show_pid: bool = True) -> html.Ul:
    """Format a list of log records as an html.Ul component.

    Args:
        logs: List of log dictionaries with keys: level, timestamp, module,
              message, and optionally pid
        show_pid: Whether to display the PID

    Returns:
        html.Ul component with formatted log entries
    """
    items = []
    for log in logs:
        content = [level_badge(log["level"])]

        content.append(f" at {log['timestamp']} ")
        content.append(f"in {log['module']}")

        if show_pid and "pid" in log:
            content.append(f" [PID {log['pid']}]")

        content.append(f":\n{log['message']}")

        items.append(
            html.Li(
                content,
                style={"white-space": "pre-wrap"},
            )
        )

    return html.Ul(items)
